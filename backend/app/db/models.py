"""SQLAlchemy models for uploaded files and extracted features.

Uses portable types (String, Float, JSON, DateTime) compatible with both SQLite and PostgreSQL.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

# Use JSONB on PostgreSQL for efficient indexing, standard JSON on SQLite
JsonType = JSON().with_variant(JSONB, "postgresql")


class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    crs: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    features: Mapped[list[Feature]] = relationship(
        "Feature",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="Feature.feature_index",
    )


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_index: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry_type: Mapped[str] = mapped_column(String(64), nullable=False)
    geometry: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    source_crs: Mapped[str] = mapped_column(String(64), nullable=False)

    measurement_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    area_sq_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    perimeter_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    geodesic_area_sq_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    geodesic_length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    measurement_crs: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    file: Mapped[File] = relationship("File", back_populates="features")

    __table_args__ = (Index("ix_features_file_feature_index", "file_id", "feature_index"),)
