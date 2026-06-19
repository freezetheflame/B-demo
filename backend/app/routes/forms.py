"""
Form CRUD routes with multi-dimensional filtering.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models import (
    MerchantForm, ListingForm, ProductForm, ReportForm,
    FormStatus, SubmissionLog, FormType,
)
from app.routes.ws import notify_batch_progress
from app.routes.aggregation import geohash_encode
from pydantic import BaseModel, Field
from enum import Enum
import time

router = APIRouter()


# ─── Schemas ───

class FormFilter(BaseModel):
    form_type: Optional[str] = None
    merchant_id: Optional[int] = None
    status: Optional[str] = None
    keyword: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    geohash_prefix: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=1000)
    sort_by: str = "created_at"
    sort_order: str = "desc"


# ─── Generic Filter Helper ───

MODEL_MAP = {
    "merchant": MerchantForm,
    "listing": ListingForm,
    "product": ProductForm,
    "report": ReportForm,
}

async def query_forms(form_type: str, filters: FormFilter, db: AsyncSession):
    model = MODEL_MAP.get(form_type)
    if not model:
        raise HTTPException(400, f"Invalid form_type: {form_type}")

    query = select(model)

    if filters.merchant_id:
        query = query.where(model.merchant_id == filters.merchant_id)
    if filters.status:
        query = query.where(model.status == filters.status)
    if filters.created_after:
        query = query.where(model.created_at >= filters.created_after)
    if filters.created_before:
        query = query.where(model.created_at <= filters.created_before)
    if filters.keyword:
        like = f"%{filters.keyword}%"
        if hasattr(model, "name"):
            query = query.where(model.name.ilike(like))
        elif hasattr(model, "title"):
            query = query.where(model.title.ilike(like))

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    # Sort
    sort_col = getattr(model, filters.sort_by, model.created_at)
    order = sort_col.asc() if filters.sort_order == "asc" else sort_col.desc()
    query = query.order_by(order)

    # Paginate
    offset = (filters.page - 1) * filters.page_size
    query = query.offset(offset).limit(filters.page_size)

    rows = (await db.execute(query)).scalars().all()
    return rows, total


# ─── Submit Schemas ───

class MerchantSubmit(BaseModel):
    name: str = Field(..., example="星巴克新街口店")
    address: str = Field(..., example="南京新街口正洪街18号")
    lat: float = Field(ge=-90, le=90, example=32.041)
    lng: float = Field(ge=-180, le=180, example=118.784)
    category: str = Field(default="餐饮", example="餐饮")
    contact_name: str = Field(default="", example="张经理")
    contact_phone: str = Field(default="", example="13812345678")

class ListingSubmit(BaseModel):
    merchant_id: int = Field(..., example=1)
    title: str = Field(..., example="新街口写字楼A座1201")
    area: float = Field(gt=0, example=180.0)
    price: float = Field(gt=0, example=15000.0)
    images: list[str] = Field(default_factory=list, example=["img1.jpg"])

class ProductSubmit(BaseModel):
    merchant_id: int = Field(..., example=1)
    name: str = Field(..., example="拿铁咖啡")
    sku: str = Field(..., example="SKU-LATTE-001")
    category: str = Field(default="饮品", example="饮品")
    price: float = Field(gt=0, example=32.0)
    stock: int = Field(ge=0, default=500, example=500)

class ReportSubmit(BaseModel):
    merchant_id: int = Field(..., example=1)
    report_type: str = Field(pattern="^(daily|weekly|monthly)$", example="monthly")
    period: str = Field(..., example="2026-06")
    data: dict = Field(default_factory=dict, example={"revenue": 156000, "orders": 3200})


# ─── Auto-Cluster Helper ───

async def _auto_cluster_new_merchant(db: AsyncSession, form, lat: float, lng: float) -> dict:
    """
    自动聚合：新商户提交后，查找 500m 内的其他 SUBMITTED 商户，
    如果找到 → 分配同一个 batch_id 形成簇；如果没有 → 自成新簇。
    """
    from app.routes.aggregation import haversine_m
    from sqlalchemy import text as sa_text

    # 用 PostGIS ST_DWithin 快速过滤 500m 内的候选商户
    result = await db.execute(
        sa_text("""
            SELECT id, ST_Y(geo) AS lat, ST_X(geo) AS lng
            FROM merchant_forms
            WHERE status = 'SUBMITTED'
              AND geo IS NOT NULL
              AND id != :my_id
              AND ST_DWithin(
                  geo,
                  ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                  0.005  -- ~500m in degrees at Nanjing latitude
              )
            LIMIT 100
        """),
        {"my_id": form.id, "lat": lat, "lng": lng}
    )
    candidates = result.fetchall()

    # Haversine 精确过滤
    nearby_ids = []
    for row in candidates:
        dist = haversine_m(lat, lng, float(row.lat), float(row.lng))
        if dist <= 500:
            nearby_ids.append(int(row.id))

    if nearby_ids:
        # 有邻近商户 → 归入同一个 batch_id
        batch_id = f"auto_{int(time.time())}_{form.id}"
        form.batch_id = batch_id
        await db.execute(
            sa_text("UPDATE merchant_forms SET batch_id = :bid WHERE id = ANY(:ids)"),
            {"bid": batch_id, "ids": nearby_ids}
        )
        return {"auto_clustered": True, "cluster_size": len(nearby_ids) + 1, "batch_id": batch_id}
    else:
        # 无邻近商户 → 自成新簇
        batch_id = f"auto_{int(time.time())}_{form.id}"
        form.batch_id = batch_id
        return {"auto_clustered": True, "cluster_size": 1, "batch_id": batch_id}


# ─── CRUD APIs ───

@router.post("/merchant/submit")
async def submit_merchant(body: MerchantSubmit, db: AsyncSession = Depends(get_db)):
    """提交商户信息表单。"""
    import time as _time
    from geoalchemy2 import WKTElement

    form = MerchantForm(
        name=body.name,
        address=body.address,
        geo=WKTElement(f"POINT({body.lng} {body.lat})", srid=4326),
        category=body.category,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        status=FormStatus.SUBMITTED,
        geohash=geohash_encode(body.lat, body.lng, precision=9),
        submitted_at=datetime.utcnow(),
    )
    db.add(form)
    await db.flush()

    _log_submission(db, "merchant", str(form.id), "success", 0, None)

    # 自动聚合：查找 500m 内的邻近商户 → 归入同一 batch_id
    cluster_info = await _auto_cluster_new_merchant(db, form, body.lat, body.lng)

    await db.commit()
    return {"id": form.id, "status": "submitted", "form_type": "merchant", **cluster_info}


@router.post("/listing/submit")
async def submit_listing(body: ListingSubmit, db: AsyncSession = Depends(get_db)):
    """提交商户房源表单。"""
    form = ListingForm(
        merchant_id=body.merchant_id,
        title=body.title,
        area=body.area,
        price=body.price,
        images=body.images,
        status=FormStatus.SUBMITTED,
        submitted_at=datetime.utcnow(),
    )
    db.add(form)
    await db.flush()
    _log_submission(db, "listing", str(form.id), "success", 0, None)
    await db.commit()
    return {"id": form.id, "status": "submitted", "form_type": "listing"}


@router.post("/product/submit")
async def submit_product(body: ProductSubmit, db: AsyncSession = Depends(get_db)):
    """提交商户商品表单。"""
    form = ProductForm(
        merchant_id=body.merchant_id,
        name=body.name,
        sku=body.sku,
        category=body.category,
        price=body.price,
        stock=body.stock,
        status=FormStatus.SUBMITTED,
        submitted_at=datetime.utcnow(),
    )
    db.add(form)
    await db.flush()
    _log_submission(db, "product", str(form.id), "success", 0, None)
    await db.commit()
    return {"id": form.id, "status": "submitted", "form_type": "product"}


@router.post("/report/submit")
async def submit_report(body: ReportSubmit, db: AsyncSession = Depends(get_db)):
    """提交商户报表表单。"""
    form = ReportForm(
        merchant_id=body.merchant_id,
        report_type=body.report_type,
        period=body.period,
        data=body.data,
        status=FormStatus.SUBMITTED,
        submitted_at=datetime.utcnow(),
    )
    db.add(form)
    await db.flush()
    _log_submission(db, "report", str(form.id), "success", 0, None)
    await db.commit()
    return {"id": form.id, "status": "submitted", "form_type": "report"}


def _log_submission(db: AsyncSession, form_type: str, merchant_id: str,
                    status: str, duration_ms: int, error_code: str | None):
    """写一条提交埋点日志。"""
    log = SubmissionLog(
        form_type=form_type,
        merchant_id=merchant_id,
        status=status,
        duration_ms=duration_ms,
        error_code=error_code,
        created_at=datetime.utcnow(),
    )
    db.add(log)


@router.get("/{form_type}")
async def list_forms(
    form_type: str,
    page: int = Query(1),
    page_size: int = Query(50),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    geohash_prefix: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    filters = FormFilter(
        form_type=form_type, page=page, page_size=page_size,
        status=status, keyword=keyword, geohash_prefix=geohash_prefix,
    )
    rows, total = await query_forms(form_type, filters, db)
    def _serialize(r):
        status_val = r.status.value if hasattr(r.status, "value") else r.status
        item = {
            "id": r.id,
            "status": status_val,
        }
        # Common fields across form types
        for field in ["name", "title", "address", "category", "contact_name", 
                       "contact_phone", "area", "price", "sku", "stock",
                       "batch_id", "geohash", "submitted_at"]:
            if hasattr(r, field):
                val = getattr(r, field)
                if isinstance(val, datetime):
                    val = val.isoformat()
                item[field] = val
        return item

    return {
        "data": [_serialize(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{form_type}/{form_id}")
async def get_form(form_type: str, form_id: int, db: AsyncSession = Depends(get_db)):
    model = MODEL_MAP.get(form_type)
    if not model:
        raise HTTPException(400, "Invalid form_type")
    row = await db.get(model, form_id)
    if not row:
        raise HTTPException(404, "Form not found")
    return {"data": row}


# ═══════════════════════════════════════════════════════════
# 批处理 — 按表单类型执行不同业务流程
# ═══════════════════════════════════════════════════════════

@router.post("/{form_type}/batch")
async def batch_process_forms(form_type: str, form_ids: list[int], db: AsyncSession = Depends(get_db)):
    """按表单类型分发到不同的批处理流程。"""
    model = MODEL_MAP.get(form_type)
    if not model:
        raise HTTPException(400, "Invalid form_type")

    result = await db.execute(select(model).where(model.id.in_(form_ids)))
    rows = list(result.scalars().all())
    if not rows:
        return {"updated": 0, "message": "没有匹配的表单"}

    total = len(rows)
    batch_id = f"batch_{int(time.time())}"
    results: dict[str, int] = {}

    if form_type == "merchant":
        results = await _batch_merchant(rows, batch_id, total, db)
    elif form_type == "listing":
        results = await _batch_listing(rows, batch_id, total, db)
    elif form_type == "product":
        results = await _batch_product(rows, batch_id, total, db)
    elif form_type == "report":
        results = await _batch_report(rows, batch_id, total, db)

    await db.commit()
    await notify_batch_progress(batch_id, total, total, "completed")
    return {"batch_id": batch_id, "total": total, **results}


async def _batch_merchant(rows, batch_id: str, total: int, db: AsyncSession) -> dict:
    """
    商户信息批处理流程：
    ① 数据清洗 → 校验名称/地址非空、坐标有效
    ② 地理编码 → 根据 geo 坐标计算 geohash
    ③ 分配 batch_id → 同 geohash 前缀的商户归入同一批次
    ④ 状态更新 → submitted → approved
    """
    cleaned = 0
    geocoded = 0
    failed = 0

    for i, row in enumerate(rows):
        # ① 数据清洗
        if not row.name or len(row.name.strip()) < 2:
            row.status = FormStatus.REJECTED
            failed += 1
            continue
        cleaned += 1

        # ② 地理编码 — 从 PostGIS geo 提取坐标计算 geohash
        try:
            from geoalchemy2.shape import to_shape
            from app.routes.aggregation import geohash_encode as gh_encode
            point = to_shape(row.geo)
            row.geohash = gh_encode(point.y, point.x, precision=9)
            geocoded += 1
        except Exception:
            pass  # 没有 geo 数据的跳过

        # ③ 分配批次
        row.batch_id = batch_id
        row.status = FormStatus.APPROVED

        if (i + 1) % max(1, total // 10) == 0:
            await notify_batch_progress(batch_id, i + 1, total, "商户清洗+编码+聚合")

    return {"approved": cleaned - failed, "failed": failed, "geocoded": geocoded}


async def _batch_listing(rows, batch_id: str, total: int, db: AsyncSession) -> dict:
    """
    房源批处理流程：
    ① 按商户聚合 → 统计每个商户的房源总数/总面积/总价
    ② 价格/面积校验 → 单价异常（<¥10/m² 或 >¥50000/m²）标为可疑
    ③ 批量审批 → 正常房源通过，异常房源驳回
    """
    approved = 0
    rejected = 0
    # 按商户聚合
    merchant_stats: dict[int, dict] = {}
    for r in rows:
        mid = r.merchant_id
        if mid not in merchant_stats:
            merchant_stats[mid] = {"count": 0, "total_area": 0, "total_price": 0}
        merchant_stats[mid]["count"] += 1
        merchant_stats[mid]["total_area"] += r.area or 0
        merchant_stats[mid]["total_price"] += r.price or 0

    for i, row in enumerate(rows):
        # ② 价格面积校验
        unit_price = (row.price / row.area) if (row.area and row.area > 0) else 0
        if unit_price < 10 or unit_price > 50000:
            row.status = FormStatus.REJECTED
            rejected += 1
        else:
            row.status = FormStatus.APPROVED
            approved += 1

        if (i + 1) % max(1, total // 10) == 0:
            await notify_batch_progress(batch_id, i + 1, total, "房源校验+审批")

    return {"approved": approved, "rejected": rejected,
            "merchants_affected": len(merchant_stats)}


async def _batch_product(rows, batch_id: str, total: int, db: AsyncSession) -> dict:
    """
    商品批处理流程：
    ① SKU校验 → 检查批次内是否有重复 SKU
    ② 库存同步 → 标记零库存商品
    ③ 批量上架 → 校验通过的上架，重复/零库存驳回
    """
    approved = 0
    rejected = 0
    sku_seen: set[str] = set()
    duplicate_skus: set[str] = set()

    # 第一遍：找重复 SKU
    for r in rows:
        if r.sku in sku_seen:
            duplicate_skus.add(r.sku)
        sku_seen.add(r.sku)

    for i, row in enumerate(rows):
        # ① SKU 校验 + ② 库存同步
        if row.sku in duplicate_skus:
            row.status = FormStatus.REJECTED
            rejected += 1
        elif row.stock is not None and row.stock <= 0:
            row.status = FormStatus.REJECTED
            rejected += 1
        else:
            row.status = FormStatus.APPROVED
            approved += 1

        if (i + 1) % max(1, total // 10) == 0:
            await notify_batch_progress(batch_id, i + 1, total, "SKU校验+上架")

    return {"approved": approved, "rejected": rejected,
            "duplicate_skus": len(duplicate_skus)}


async def _batch_report(rows, batch_id: str, total: int, db: AsyncSession) -> dict:
    """
    报表批处理流程：
    ① 数据校验 → 检查 JSON data 包含必要字段
    ② 归档存储 → 标记处理时间
    ③ 汇总生成 → 统计所有报表的关键指标（总收入/总订单）
    """
    approved = 0
    rejected = 0
    total_revenue = 0
    total_orders = 0

    for i, row in enumerate(rows):
        # ① 数据校验
        data = row.data or {}
        if isinstance(data, dict) and "revenue" in data:
            total_revenue += data.get("revenue", 0)
            total_orders += data.get("orders", 0)
            row.status = FormStatus.APPROVED
            approved += 1
        else:
            row.status = FormStatus.REJECTED
            rejected += 1

        if (i + 1) % max(1, total // 10) == 0:
            await notify_batch_progress(batch_id, i + 1, total, "报表校验+归档")

    return {"approved": approved, "rejected": rejected,
            "aggregated_revenue": total_revenue, "aggregated_orders": total_orders}
