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
from pydantic import BaseModel, Field
from enum import Enum

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


# ─── CRUD APIs ───

@router.post("/{form_type}/submit")
async def submit_form(form_type: str, db: AsyncSession = Depends(get_db)):
    """Submit a new form (placeholder - actual data from request body in real impl)."""
    return {"message": f"Form {form_type} submitted", "status": "ok"}


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
    return {
        "data": [{"id": r.id, "status": r.status.value if hasattr(r.status, "value") else r.status}
                 for r in rows],
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
    """Batch update form statuses."""
    model = MODEL_MAP.get(form_type)
    if not model:
        raise HTTPException(400, "Invalid form_type")
    result = await db.execute(
        select(model).where(model.id.in_(form_ids))
    )
    rows = result.scalars().all()
    for row in rows:
        row.status = FormStatus.PROCESSING
    return {"updated": len(rows)}
