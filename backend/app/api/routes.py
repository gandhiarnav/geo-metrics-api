"""API route handlers for geospatial file ingestion, metadata, and measurements."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_repository
from app.api.schemas import (
    FeaturesResponse,
    FileListResponse,
    FileResponse,
    MeasurementsResponse,
    MeasurementSummarySchema,
)
from app.core.config import Settings
from app.core.errors import (
    FileNotReadyError,
    InvalidFileError,
    NotFoundError,
    UploadTooLargeError,
)
from app.db.repository import FileRepository
from app.domain import FileStatus
from app.services.ingest import ingest_file

router = APIRouter(prefix="/api/files", tags=["files"])


def _read_upload_safely(upload: UploadFile, max_bytes: int, chunk_size: int) -> bytes:
    """Stream upload into memory up to max_bytes limit, aborting with 413 if exceeded."""
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = upload.file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            limit_mb = max_bytes / (1024 * 1024)
            raise UploadTooLargeError(
                f"File size exceeds maximum upload limit of {limit_mb:.1f} MB",
                details={"max_bytes": max_bytes, "actual_bytes": total},
            )
        chunks.append(chunk)

    return b"".join(chunks)


@router.post(
    "/",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a geospatial file",
    description="Upload a KML (.kml), KMZ (.kmz), or Shapefile (.zip) for measurement.",
)
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> FileResponse:
    settings: Settings = request.app.state.settings
    filename = file.filename or "uploaded_file"

    data = _read_upload_safely(
        upload=file,
        max_bytes=settings.max_upload_bytes,
        chunk_size=settings.upload_chunk_bytes,
    )

    record = ingest_file(data, filename, session=session, settings=settings)
    return FileResponse.model_validate(record)


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List all uploaded files",
    description="Retrieve paginated list of uploaded geospatial files ordered by creation date.",
)
def list_files(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    repo: FileRepository = Depends(get_repository),
) -> FileListResponse:
    files, total = repo.list_files(limit=limit, offset=offset)
    return FileListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[FileResponse.model_validate(f) for f in files],
    )


@router.get(
    "/{file_id}/",
    response_model=FileResponse,
    summary="Retrieve file metadata and processing status",
    description="Retrieve status, CRS, and feature count for an uploaded geospatial file.",
)
def get_file(
    file_id: str,
    repo: FileRepository = Depends(get_repository),
) -> FileResponse:
    record = repo.get_file(file_id)
    if record is None:
        raise NotFoundError(f"File '{file_id}' not found")
    return FileResponse.model_validate(record)


@router.get(
    "/{file_id}/measurements/",
    response_model=MeasurementsResponse,
    summary="Retrieve computed measurements and whole-file summary",
    description=(
        "Retrieve paginated measurements (area in m², length in m) alongside "
        "whole-file aggregate statistics (independent of limit/offset)."
    ),
)
def get_file_measurements(
    file_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    repo: FileRepository = Depends(get_repository),
) -> MeasurementsResponse:
    record = repo.get_file(file_id)
    if record is None:
        raise NotFoundError(f"File '{file_id}' not found")

    if record.status == FileStatus.PROCESSING.value:
        raise FileNotReadyError("File is currently being processed")
    if record.status == FileStatus.FAILED.value:
        raise InvalidFileError(f"File processing failed: {record.error}")

    features, summary_dict, total = repo.get_file_measurements(
        file_id=file_id, limit=limit, offset=offset
    )

    return MeasurementsResponse(
        file_id=file_id,
        source_crs=record.crs,
        summary=MeasurementSummarySchema(**summary_dict),
        total=total,
        limit=limit,
        offset=offset,
        measurements=features,
    )


@router.get(
    "/{file_id}/features/",
    response_model=FeaturesResponse,
    summary="Retrieve paginated GeoJSON features",
    description="Retrieve paginated feature geometries in native CRS and attribute properties.",
)
def get_file_features(
    file_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    repo: FileRepository = Depends(get_repository),
) -> FeaturesResponse:
    record = repo.get_file(file_id)
    if record is None:
        raise NotFoundError(f"File '{file_id}' not found")

    if record.status == FileStatus.PROCESSING.value:
        raise FileNotReadyError("File is currently being processed")
    if record.status == FileStatus.FAILED.value:
        raise InvalidFileError(f"File processing failed: {record.error}")

    features, total = repo.get_file_features(file_id=file_id, limit=limit, offset=offset)

    return FeaturesResponse(
        file_id=file_id,
        total=total,
        limit=limit,
        offset=offset,
        features=features,
    )
