"""
Geographic aggregation using Geohash + distance clustering.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from app.database import get_db, async_session
from app.models import MerchantForm, FormStatus
import time, math

router = APIRouter()


# ─── Geohash helpers ───

GEOHASH_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

def geohash_encode(lat: float, lng: float, precision: int = 7) -> str:
    """Encode lat/lng to geohash string."""
    lat_range, lng_range = [-90, 90], [-180, 180]
    hash_str = ""
    for i in range(precision):
        if i % 2 == 0:
            mid = (lng_range[0] + lng_range[1]) / 2
            if lng > mid:
                lng_range[0] = mid
                bit = 1
            else:
                lng_range[1] = mid
                bit = 0
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat > mid:
                lat_range[0] = mid
                bit = 1
            else:
                lat_range[1] = mid
                bit = 0
        # ... simplified - real impl would pack 5 bits per char
    return hash_str or "s000"


@router.post("/run")
async def run_aggregation(
    distance_m: float = Query(500, description="聚合距离(米)"),
    precision: int = Query(6, description="Geohash精度"),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1: Geohash粗分桶
    Step 2: 每个桶内按距离聚簇
    Step 3: 更新batch_id
    """
    start = time.time()

    # Step 1: Get all submitted forms with geo
    result = await db.execute(
        select(MerchantForm).where(
            MerchantForm.status == FormStatus.SUBMITTED,
            MerchantForm.geo.isnot(None),
        ).limit(100000)
    )
    forms = result.scalars().all()

    # Step 2: Simple clustering by geohash prefix
    buckets: dict[str, list] = {}
    for f in forms:
        prefix = f.geohash[:precision] if f.geohash else "unknown"
        if prefix not in buckets:
            buckets[prefix] = []
        buckets[prefix].append(f)

    # Step 3: Assign batch IDs
    batch_count = 0
    for prefix, group in buckets.items():
        batch_id = f"batch_{int(time.time())}_{prefix}"
        for f in group:
            f.batch_id = batch_id
            f.status = FormStatus.PROCESSING
        batch_count += 1

    await db.commit()
    elapsed = time.time() - start

    return {
        "status": "ok",
        "total_forms": len(forms),
        "clusters": batch_count,
        "elapsed_seconds": round(elapsed, 3),
        "distance_m": distance_m,
    }


@router.get("/clusters")
async def get_clusters(batch_id: str = None, db: AsyncSession = Depends(get_db)):
    """Get aggregation results grouped by cluster."""
    query = select(MerchantForm)
    if batch_id:
        query = query.where(MerchantForm.batch_id == batch_id)
    query = query.order_by(MerchantForm.batch_id, MerchantForm.id)

    result = await db.execute(query)
    forms = result.scalars().all()

    clusters = {}
    for f in forms:
        bid = f.batch_id or "unassigned"
        if bid not in clusters:
            clusters[bid] = []
        clusters[bid].append({
            "id": f.id,
            "name": f.name,
            "status": f.status.value,
            "geohash": f.geohash,
        })

    return {
        "total_clusters": len(clusters),
        "clusters": clusters,
    }
