from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum, ForeignKey, JSON, Boolean, Index, func
from sqlalchemy.orm import DeclarativeBase
from geoalchemy2 import Geometry
import enum
import datetime


class Base(DeclarativeBase):
    pass


# ─── Enums ───

class FormStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"


class FormType(str, enum.Enum):
    MERCHANT = "merchant"
    LISTING = "listing"
    PRODUCT = "product"
    REPORT = "report"


# ─── Merchant Form ───

class MerchantForm(Base):
    __tablename__ = "merchant_forms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False, comment="商户名称")
    address = Column(String(512), nullable=False, comment="地址")
    geo = Column(Geometry("POINT", srid=4326), comment="地理坐标")
    category = Column(String(128), comment="行业分类")
    contact_name = Column(String(128), comment="联系人")
    contact_phone = Column(String(32), comment="联系电话")
    status = Column(Enum(FormStatus), default=FormStatus.DRAFT)
    batch_id = Column(String(64), index=True, comment="聚合批次ID")
    geohash = Column(String(32), index=True, comment="Geohash前缀")
    submitted_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_merchant_geo", "geo", postgresql_using="gist"),
        Index("idx_merchant_geohash_status", "geohash", "status"),
    )


# ─── Listing Form ───

class ListingForm(Base):
    __tablename__ = "listing_forms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(Integer, ForeignKey("merchant_forms.id"), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    area = Column(Float, comment="面积(m²)")
    price = Column(Float, comment="价格(元)")
    geo = Column(Geometry("POINT", srid=4326), comment="地理坐标")
    images = Column(JSON, default=list)
    status = Column(Enum(FormStatus), default=FormStatus.DRAFT)
    geohash = Column(String(32), index=True)
    submitted_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_listing_geo", "geo", postgresql_using="gist"),)


# ─── Product Form ───

class ProductForm(Base):
    __tablename__ = "product_forms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(Integer, ForeignKey("merchant_forms.id"), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    sku = Column(String(128), index=True, comment="SKU编码")
    category = Column(String(128))
    price = Column(Float)
    stock = Column(Integer, default=0)
    status = Column(Enum(FormStatus), default=FormStatus.DRAFT)
    submitted_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── Report Form ───

class ReportForm(Base):
    __tablename__ = "report_forms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(Integer, ForeignKey("merchant_forms.id"), nullable=False, index=True)
    report_type = Column(String(64), comment="报表类型: daily/weekly/monthly")
    period = Column(String(32), comment="统计周期: 2026-06")
    data = Column(JSON, comment="报表数据")
    file_url = Column(String(512), comment="文件存储路径")
    status = Column(Enum(FormStatus), default=FormStatus.DRAFT)
    submitted_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── Knowledge Documents ───

class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(String(64), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    category = Column(String(128))
    version = Column(Integer, default=1)
    status = Column(String(32), default="draft")  # draft | published | archived
    created_by = Column(String(128))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)


class KnowledgeDocVersion(Base):
    __tablename__ = "knowledge_doc_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("knowledge_docs.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    diff_json = Column(JSON)
    operated_by = Column(String(128))
    operated_at = Column(DateTime, server_default=func.now())


# ─── Submission Log (Statistics) ───

class SubmissionLog(Base):
    __tablename__ = "submission_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    form_type = Column(String(32), nullable=False, index=True)
    merchant_id = Column(String(64), index=True)
    status = Column(String(32), nullable=False)  # start | success | fail | timeout
    duration_ms = Column(Integer)
    error_code = Column(String(32))
    error_msg = Column(Text)
    geo_hash = Column(String(32))
    batch_id = Column(String(64))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_submit_log_lookup", "form_type", "status", "created_at"),
    )
