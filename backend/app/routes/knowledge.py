"""
Knowledge document CRUD with version management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from datetime import datetime
from app.database import get_db
from app.models import KnowledgeDoc, KnowledgeDocVersion
from pydantic import BaseModel

router = APIRouter()


# ─── Schemas ───

class DocCreate(BaseModel):
    merchant_id: str
    title: str
    content: str
    tags: list[str] = []
    category: str = "general"


class DocUpdate(BaseModel):
    title: str = None
    content: str = None
    tags: list[str] = None
    category: str = None
    status: str = None


# ─── CRUD ───

@router.post("/docs")
async def create_doc(doc: DocCreate, db: AsyncSession = Depends(get_db)):
    new_doc = KnowledgeDoc(
        merchant_id=doc.merchant_id,
        title=doc.title,
        content=doc.content,
        tags=doc.tags,
        category=doc.category,
    )
    db.add(new_doc)
    await db.flush()

    # Create initial version
    version = KnowledgeDocVersion(
        doc_id=new_doc.id,
        version=1,
        content=doc.content,
    )
    db.add(version)
    return {"id": new_doc.id, "version": 1, "status": "created"}


@router.get("/docs")
async def list_docs(
    merchant_id: str = None,
    category: str = None,
    keyword: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeDoc).where(KnowledgeDoc.deleted_at.is_(None))

    if merchant_id:
        query = query.where(KnowledgeDoc.merchant_id == merchant_id)
    if category:
        query = query.where(KnowledgeDoc.category == category)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            or_(KnowledgeDoc.title.ilike(like), KnowledgeDoc.content.ilike(like))
        )

    # Count
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(KnowledgeDoc.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(query)).scalars().all()
    return {
        "data": [{"id": r.id, "title": r.title, "category": r.category, "status": r.status,
                   "version": r.version, "updated_at": r.updated_at.isoformat()} for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/docs/{doc_id}")
async def get_doc(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc or doc.deleted_at:
        raise HTTPException(404, "Document not found")
    return {
        "id": doc.id, "title": doc.title, "content": doc.content,
        "tags": doc.tags, "category": doc.category, "version": doc.version,
        "status": doc.status, "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }


@router.put("/docs/{doc_id}")
async def update_doc(doc_id: int, update: DocUpdate, db: AsyncSession = Depends(get_db)):
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc or doc.deleted_at:
        raise HTTPException(404, "Document not found")

    old_content = doc.content
    update_data = update.model_dump(exclude_none=True)
    for key, val in update_data.items():
        setattr(doc, key, val)

    doc.version += 1
    new_version = KnowledgeDocVersion(
        doc_id=doc_id,
        version=doc.version,
        content=update.content or old_content,
    )
    db.add(new_version)
    return {"id": doc_id, "version": doc.version, "status": "updated"}


@router.delete("/docs/{doc_id}")
async def delete_doc(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(KnowledgeDoc, doc_id)
    if not doc or doc.deleted_at:
        raise HTTPException(404, "Document not found")
    doc.deleted_at = datetime.utcnow()
    doc.status = "archived"
    return {"id": doc_id, "status": "deleted"}


@router.get("/docs/{doc_id}/versions")
async def get_doc_versions(doc_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(KnowledgeDocVersion)
        .where(KnowledgeDocVersion.doc_id == doc_id)
        .order_by(KnowledgeDocVersion.version.desc())
        .limit(50)
    )
    versions = result.scalars().all()
    return {
        "data": [{"version": v.version, "operated_at": v.operated_at.isoformat(),
                   "operated_by": v.operated_by} for v in versions]
    }
