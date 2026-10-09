"""Database repository for File and Feature queries with whole-file SQL aggregations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import Feature, File


class FileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_file(self, file_record: File) -> File:
        self.session.add(file_record)
        return file_record

    def get_file(self, file_id: str) -> File | None:
        return self.session.get(File, file_id)

    def list_files(self, limit: int = 50, offset: int = 0) -> tuple[list[File], int]:
        total_stmt = select(func.count()).select_from(File)
        total = self.session.scalar(total_stmt) or 0

        stmt = select(File).order_by(File.created_at.desc()).offset(offset).limit(limit)
        files = list(self.session.scalars(stmt).all())
        return files, total

    def get_file_features(
        self, file_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[Feature], int]:
        total_stmt = select(func.count()).select_from(Feature).where(Feature.file_id == file_id)
        total = self.session.scalar(total_stmt) or 0

        stmt = (
            select(Feature)
            .where(Feature.file_id == file_id)
            .order_by(Feature.feature_index.asc())
            .offset(offset)
            .limit(limit)
        )
        features = list(self.session.scalars(stmt).all())
        return features, total

    def get_file_measurements(
        self, file_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[list[Feature], dict[str, Any], int]:
        """Fetch paginated measurements alongside a whole-file aggregate summary."""

        # 1. Whole-file SQL aggregation (independent of limit/offset)
        def _count_status(status_val: str) -> Any:
            return func.count(case((Feature.measurement_status == status_val, 1)))

        summary_stmt = select(
            func.count().label("total"),
            _count_status("MEASURED").label("measured_count"),
            _count_status("NOT_APPLICABLE").label("not_applicable_count"),
            _count_status("UNSUPPORTED").label("unsupported_count"),
            _count_status("ERROR").label("error_count"),
            func.coalesce(func.sum(Feature.area_sq_m), 0.0).label("total_area_sq_m"),
            func.coalesce(func.sum(Feature.length_m), 0.0).label("total_length_m"),
        ).where(Feature.file_id == file_id)

        row = self.session.execute(summary_stmt).one()
        summary = {
            "feature_count": row.total,
            "measured_count": row.measured_count,
            "not_applicable_count": row.not_applicable_count,
            "unsupported_count": row.unsupported_count,
            "error_count": row.error_count,
            "total_area_sq_m": round(float(row.total_area_sq_m), 2),
            "total_length_m": round(float(row.total_length_m), 2),
        }

        # 2. Paginated feature measurements
        stmt = (
            select(Feature)
            .where(Feature.file_id == file_id)
            .order_by(Feature.feature_index.asc())
            .offset(offset)
            .limit(limit)
        )
        features = list(self.session.scalars(stmt).all())
        return features, summary, row.total
