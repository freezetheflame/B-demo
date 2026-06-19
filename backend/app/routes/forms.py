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


# ─── CRUD APIs ───

@router.post("/{form_type}/submit")
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
    await db.commit()

    return {"id": form.id, "status": "submitted", "form_type": "merchant"}


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


@router.post("/{form_type}/batch")
async def batch_process_forms(form_type: str, form_ids: list[int], db: AsyncSession = Depends(get_db)):
    """Batch update form statuses with WebSocket progress."""
    model = MODEL_MAP.get(form_type)
    if not model:
        raise HTTPException(400, "Invalid form_type")
    result = await db.execute(
        select(model).where(model.id.in_(form_ids))
    )
    rows = result.scalars().all()

    total = len(rows)
    batch_id = f"batch_{int(time.time())}"
    chunk_size = max(1, total // 10)  # ~10 progress updates

    for i, row in enumerate(rows):
        row.status = FormStatus.PROCESSING
        if (i + 1) % chunk_size == 0 or i == total - 1:
            await notify_batch_progress(batch_id, i + 1, total, "processing")

    await db.commit()
    await notify_batch_progress(batch_id, total, total, "completed")
    return {"updated": total, "batch_id": batch_id}
