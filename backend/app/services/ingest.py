"""Ingestion orchestrator: parses, measures, and persists geospatial files atomically."""

from __future__ import annotations

import datetime
import os
import uuid

import shapely
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import (
    InvalidFileError,
    UnsupportedFormatError,
    UploadTooLargeError,
)
from app.db.models import Feature, File
from app.db.repository import FileRepository
from app.domain import FileStatus
from app.geo.crs import crs_label
from app.geo.measure import GeometryMeasurer
from app.parsers.base import ALLOWED_EXTENSIONS, parse_geospatial_file


def _round(val: float | None) -> float | None:
    return round(val, 2) if val is not None else None


def ingest_file(
    data: bytes,
    filename: str,
    session: Session,
    settings: Settings | None = None,
) -> File:
    """Ingest, measure, and persist a geospatial file in a managed transaction.

    Pre-ingestion checks (extension and upload size limits) reject invalid requests
    before database record creation. Once accepted, file status transitions through
    PROCESSING -> COMPLETED | FAILED atomically.
    """
    settings = settings or get_settings()
    repo = FileRepository(session)

    # 1. Pre-validation: check extension and size
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"Unsupported file format '{ext}'. Allowed: .kml, .kmz, .zip",
            details={"allowed_extensions": sorted(ALLOWED_EXTENSIONS), "filename": filename},
        )

    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / (1024 * 1024)
        raise UploadTooLargeError(
            f"File size exceeds maximum upload limit of {limit_mb:.1f} MB",
            details={"max_bytes": settings.max_upload_bytes, "actual_bytes": len(data)},
        )

    file_id = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.UTC)

    # Initial file record
    file_record = File(
        id=file_id,
        filename=filename,
        file_type=ext.lstrip("."),
        crs="UNKNOWN",
        status=FileStatus.PROCESSING.value,
        feature_count=0,
        warnings=[],
        error=None,
        created_at=now,
    )
    repo.add_file(file_record)
    session.flush()

    try:
        # 2. Parse file
        parsed = parse_geospatial_file(data, filename, settings)
        file_record.file_type = parsed.file_type.value
        source_crs_str = crs_label(parsed.crs)
        file_record.crs = source_crs_str

        # 3. Measure geometries
        measurer = GeometryMeasurer(parsed.crs)
        features_to_add: list[Feature] = []

        for parsed_feature in parsed.features:
            measurement = measurer.measure(parsed_feature.geometry)

            geom_geojson = None
            if parsed_feature.geometry is not None and not parsed_feature.geometry.is_empty:
                try:
                    geom_geojson = shapely.geometry.mapping(parsed_feature.geometry)
                except Exception:
                    geom_geojson = None

            # Combine messages if both parser and measurer had notes
            combined_msg: str | None = None
            msgs = [m for m in (parsed_feature.message, measurement.message) if m]
            if msgs:
                combined_msg = "; ".join(msgs)

            feature_row = Feature(
                id=uuid.uuid4().hex,
                file_id=file_id,
                feature_index=parsed_feature.index,
                geometry_type=parsed_feature.geometry_type,
                geometry=geom_geojson,
                properties=parsed_feature.properties,
                source_crs=source_crs_str,
                measurement_status=measurement.status.value,
                area_sq_m=_round(measurement.area_sq_m),
                length_m=_round(measurement.length_m),
                perimeter_m=_round(measurement.perimeter_m),
                geodesic_area_sq_m=_round(measurement.geodesic_area_sq_m),
                geodesic_length_m=_round(measurement.geodesic_length_m),
                measurement_crs=measurement.measurement_crs,
                message=combined_msg,
                created_at=now,
            )
            features_to_add.append(feature_row)

        session.add_all(features_to_add)

        file_record.feature_count = len(parsed.features)
        file_record.warnings = parsed.warnings
        file_record.status = FileStatus.COMPLETED.value
        file_record.processed_at = datetime.datetime.now(datetime.UTC)
        session.commit()
        return file_record

    except InvalidFileError as exc:
        file_record.status = FileStatus.FAILED.value
        file_record.error = exc.message
        file_record.processed_at = datetime.datetime.now(datetime.UTC)
        session.commit()
        exc.details["file_id"] = file_id
        raise

    except Exception as exc:
        session.rollback()
        file_record.status = FileStatus.FAILED.value
        file_record.error = f"Ingestion failed: {exc}"
        file_record.processed_at = datetime.datetime.now(datetime.UTC)
        session.commit()
        raise
