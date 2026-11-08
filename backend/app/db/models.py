from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonB = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class ComponentRow(Base):
    __tablename__ = "components"
    __table_args__ = (
        UniqueConstraint("category", "brand", "model", name="uq_component_identity"),
        Index("ix_components_category", "category"),
        Index("ix_components_specs", "specs", postgresql_using="gin"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(20))
    brand: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    specs: Mapped[dict[str, Any]] = mapped_column(JsonB)
    perf_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    perf_multicore: Mapped[float | None] = mapped_column(Float, nullable=True)
    perf_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    price_rub: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    price_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str] = mapped_column(String(20))
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[Any] = mapped_column(Vector(384), nullable=True)
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class RequestRow(Base):
    __tablename__ = "requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    parsed_requirements: Mapped[dict[str, Any]] = mapped_column(JsonB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BuildRow(Base):
    __tablename__ = "builds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"), nullable=True)
    label: Mapped[str] = mapped_column(Text)
    items: Mapped[list[Any]] = mapped_column(JsonB)
    total_price: Mapped[float] = mapped_column(Numeric)
    estimated_power_w: Mapped[float] = mapped_column(Float)
    psu_recommended_w: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(JsonB)
    extra: Mapped[dict[str, Any]] = mapped_column(JsonB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatMessageRow(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    build_id: Mapped[int] = mapped_column(ForeignKey("builds.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
