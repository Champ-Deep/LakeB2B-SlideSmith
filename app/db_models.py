"""
SQLAlchemy ORM models for Postgres persistence.
Separate from Pydantic models in models.py to avoid breaking existing code.
"""
import datetime
from sqlalchemy import String, Text, Integer, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="processing")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    is_single: Mapped[bool] = mapped_column(Boolean, default=False)
    original_file: Mapped[str] = mapped_column(String(512), default="")
    output_file: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(16), index=True)
    row_index: Mapped[int] = mapped_column(Integer)
    company_name: Mapped[str] = mapped_column(String(256))
    industry: Mapped[str] = mapped_column(String(256), default="")
    contact_name: Mapped[str] = mapped_column(String(256), default="")
    contact_title: Mapped[str] = mapped_column(String(256), default="")
    website_url: Mapped[str] = mapped_column(String(512), default="")
    extra_context: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GeneratedDeck(Base):
    __tablename__ = "generated_decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(16), index=True)
    company_name: Mapped[str] = mapped_column(String(256), index=True)
    contact_name: Mapped[str] = mapped_column(String(256), default="")
    deck_url: Mapped[str] = mapped_column(String(1024), default="")
    pptx_url: Mapped[str] = mapped_column(String(1024), default="")
    pdf_url: Mapped[str] = mapped_column(String(1024), default="")
    gamma_id: Mapped[str] = mapped_column(String(128), default="")
    research_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pitch_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mapped_services: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ResearchCache(Base):
    __tablename__ = "research_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name_normalized: Mapped[str] = mapped_column(
        String(256), unique=True, index=True
    )
    research_data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
