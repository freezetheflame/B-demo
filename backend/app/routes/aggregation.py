"""
Geographic aggregation using Geohash + distance clustering.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from app.database import get_db
from app.models import MerchantForm, FormStatus
import time, math
from collections import defaultdict

router = APIRouter()

# ─── Geohash ───

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

def geohash_encode(lat: float, lng: float, precision: int = 12) -> str:
    """Encode lat/lng to a geohash string of `precision` characters.
    
    Each character encodes 5 bits = 2.5 bisections of lng/lat.
    precision=6  → ±0.61 km accuracy
    precision=7  → ±0.076 km
    precision=12 → ±0.000019 km (centimeter-level)
    """
    lat_min, lat_max = -90.0, 90.0
    lng_min, lng_max = -180.0, 180.0
    bits = 0
    bit_count = 0
    hash_chars = []
    even = True  # lng comes first

    while len(hash_chars) < precision:
        if even:
            mid = (lng_min + lng_max) / 2
            if lng > mid:
                bits = (bits << 1) | 1
                lng_min = mid
            else:
                bits = (bits << 1) | 0
                lng_max = mid
        else:
            mid = (lat_min + lat_max) / 2
            if lat > mid:
                bits = (bits << 1) | 1
                lat_min = mid
            else:
                bits = (bits << 1) | 0
                lat_max = mid

        even = not even
        bit_count += 1
        if bit_count == 5:
            hash_chars.append(BASE32[bits])
            bits = 0
            bit_count = 0

    return ''.join(hash_chars)


# ─── Distance ───

def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance in meters between two lat/lng points."""
    R = 6_371_000  # Earth radius (m)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── Clustering ───

def cluster_by_distance(points: list[tuple[int, float, float]], distance_m: float
                        ) -> dict[str, list[tuple[int, float, float]]]:
    """Group points into connected-component clusters using distance threshold.
    
    points: list of (form_id, lat, lng)
    distance_m: max distance in meters to consider two points connected
    Returns: dict of cluster_name → [(id, lat, lng), ...]
    """
    n = len(points)
    if n <= 1:
        return {f"cluster_0": points} if n == 1 else {}

    # Build adjacency for points within distance_m
    adj = defaultdict(list)
    for i in range(n):
        lat_i, lng_i = points[i][1], points[i][2]
        for j in range(i + 1, n):
            lat_j, lng_j = points[j][1], points[j][2]
            if haversine_m(lat_i, lng_i, lat_j, lng_j) <= distance_m:
                adj[i].append(j)
                adj[j].append(i)

    # Connected components via DFS
    visited = set()
    clusters: dict[str, list[tuple[int, float, float]]] = {}
    cluster_idx = 0

    for i in range(n):
        if i in visited:
            continue
        stack = [i]
        component = []
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(points[node])
            for neighbor in adj[node]:
                if neighbor not in visited:
                    stack.append(neighbor)
        clusters[f"cluster_{cluster_idx}"] = component
        cluster_idx += 1

    return clusters


# ─── Routes ───

@router.post("/run")
async def run_aggregation(
    distance_m: float = Query(500, description="聚合距离(米)"),
    precision: int = Query(5, description="Geohash精度(字符数)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1: Load submitted forms with geo → compute real geohash
    Step 2: Geohash rough bucketing (by prefix)
    Step 3: Haversine distance clustering within each bucket
    Step 4: Update batch_id and geohash in DB
    """
    start = time.time()

    # Step 1: Get SUBMITTED forms with geo coordinates (raw SQL for ST_X/ST_Y)
    result = await db.execute(
        text("""
            SELECT id, ST_Y(geo) AS lat, ST_X(geo) AS lng
            FROM merchant_forms
            WHERE status = 'SUBMITTED' AND geo IS NOT NULL
            LIMIT 100000
        """)
    )
    rows = result.fetchall()

    if not rows:
        return {
            "status": "ok",
            "total_forms": 0,
            "clusters": 0,
            "elapsed_seconds": 0,
            "distance_m": distance_m,
            "message": "没有待聚合的 SUBMITTED 表单",
        }

    # Compute geohash for each form
    form_points: list[tuple[int, float, float, str]] = []
    for row in rows:
        fid, lat, lng = int(row[0]), float(row[1]), float(row[2])
        gh = geohash_encode(lat, lng, precision=9)  # full precision for DB storage
        form_points.append((fid, lat, lng, gh))

    # Step 2: Bucket by geohash prefix
    buckets: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    for fid, lat, lng, gh in form_points:
        prefix = gh[:precision]
        buckets[prefix].append((fid, lat, lng))

    # Step 3: Cluster within each bucket
    total_clusters = 0
    batch_updates: dict[int, dict] = {}  # form_id → {batch_id, geohash, status}

    for prefix, pts in buckets.items():
        clusters = cluster_by_distance(pts, distance_m)
        for cl_name, cl_pts in clusters.items():
            batch_id = f"batch_{int(time.time())}_{prefix}_{cl_name}"
            for fid, lat, lng in cl_pts:
                batch_updates[fid] = {
                    "batch_id": batch_id,
                    "geohash": geohash_encode(lat, lng, precision=9),
                    "status": FormStatus.PROCESSING,
                }
            total_clusters += 1

    # Step 4: Batch update DB
    if batch_updates:
        for fid, updates in batch_updates.items():
            await db.execute(
                text("""
                    UPDATE merchant_forms
                    SET batch_id = :bid, geohash = :gh, status = :st
                    WHERE id = :id
                """),
                {"bid": updates["batch_id"], "gh": updates["geohash"],
                 "st": updates["status"].name, "id": fid}
            )
        await db.commit()

    elapsed = time.time() - start
    return {
        "status": "ok",
        "total_forms": len(form_points),
        "clusters": total_clusters,
        "elapsed_seconds": round(elapsed, 3),
        "distance_m": distance_m,
        "precision": precision,
        "buckets": len(buckets),
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

    clusters: dict[str, list] = {}
    for f in forms:
        bid = f.batch_id or "unassigned"
        if bid not in clusters:
            clusters[bid] = []
        clusters[bid].append({
            "id": f.id,
            "name": f.name,
            "status": f.status.value if hasattr(f.status, 'value') else str(f.status),
            "geohash": f.geohash,
        })

    return {
        "total_clusters": len(clusters),
        "clusters": clusters,
    }
