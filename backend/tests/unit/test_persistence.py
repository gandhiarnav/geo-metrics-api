from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import InvalidFileError, UnsupportedFormatError
from app.db.base import Base
from app.db.models import Feature, File
from app.db.repository import FileRepository
from app.domain import FileStatus, MeasurementStatus
from app.services.ingest import ingest_file
from tests.unit.test_kml import SAMPLE_KML
from tests.unit.test_shapefile import build_shapefile_zip


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """In-memory SQLite database session fixture."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_repository_crud_and_sql_aggregation(db_session: Session) -> None:
    repo = FileRepository(db_session)

    # 1. Add file
    file_record = File(
        id="f1",
        filename="test.kml",
        file_type="kml",
        crs="EPSG:4326",
        status=FileStatus.COMPLETED.value,
        feature_count=3,
        warnings=["Sample warning"],
    )
    repo.add_file(file_record)

    # 2. Add features (1 Polygon, 1 LineString, 1 Point)
    feat1 = Feature(
        id="feat1",
        file_id="f1",
        feature_index=0,
        geometry_type="Polygon",
        geometry={"type": "Polygon", "coordinates": []},
        properties={"name": "P1"},
        source_crs="EPSG:4326",
        measurement_status=MeasurementStatus.MEASURED.value,
        area_sq_m=5000.0,
        length_m=None,
    )
    feat2 = Feature(
        id="feat2",
        file_id="f1",
        feature_index=1,
        geometry_type="LineString",
        geometry={"type": "LineString", "coordinates": []},
        properties={"name": "L1"},
        source_crs="EPSG:4326",
        measurement_status=MeasurementStatus.MEASURED.value,
        area_sq_m=None,
        length_m=1200.0,
    )
    feat3 = Feature(
        id="feat3",
        file_id="f1",
        feature_index=2,
        geometry_type="Point",
        geometry={"type": "Point", "coordinates": []},
        properties={"name": "Pt1"},
        source_crs="EPSG:4326",
        measurement_status=MeasurementStatus.NOT_APPLICABLE.value,
        area_sq_m=None,
        length_m=None,
    )
    db_session.add_all([feat1, feat2, feat3])
    db_session.commit()

    # 3. Retrieve file
    retrieved = repo.get_file("f1")
    assert retrieved is not None
    assert retrieved.filename == "test.kml"

    # 4. List files pagination
    files, total_files = repo.list_files(limit=10, offset=0)
    assert total_files == 1
    assert len(files) == 1

    # 5. Get features pagination
    features, total_feats = repo.get_file_features("f1", limit=2, offset=0)
    assert total_feats == 3
    assert len(features) == 2
    assert features[0].feature_index == 0
    assert features[1].feature_index == 1

    # 6. SQL whole-file aggregate summary (assert summary numbers are true even with limit=1)
    meas_rows, summary, total_m = repo.get_file_measurements("f1", limit=1, offset=0)
    assert total_m == 3
    assert len(meas_rows) == 1
    assert summary["feature_count"] == 3
    assert summary["measured_count"] == 2
    assert summary["not_applicable_count"] == 1
    assert summary["error_count"] == 0
    assert summary["total_area_sq_m"] == 5000.0
    assert summary["total_length_m"] == 1200.0


def test_ingest_kml_service(db_session: Session) -> None:
    file_record = ingest_file(SAMPLE_KML, "survey.kml", session=db_session)

    assert file_record.status == FileStatus.COMPLETED.value
    assert file_record.feature_count == 4
    assert file_record.crs == "EPSG:4326"
    assert file_record.processed_at is not None

    repo = FileRepository(db_session)
    features, total = repo.get_file_features(file_record.id)
    assert total == 4

    # Verify features and measurements
    poly_feat = features[0]
    assert poly_feat.geometry_type == "Polygon"
    assert poly_feat.measurement_status == MeasurementStatus.MEASURED.value
    assert poly_feat.area_sq_m is not None
    assert poly_feat.area_sq_m > 0
    assert poly_feat.properties["crop"] == "Rice"
    assert poly_feat.geometry is not None
    assert poly_feat.geometry["type"] == "Polygon"

    road_feat = features[2]
    assert road_feat.geometry_type == "LineString"
    assert road_feat.measurement_status == MeasurementStatus.MEASURED.value
    assert road_feat.length_m is not None
    assert road_feat.length_m > 0

    point_feat = features[3]
    assert point_feat.geometry_type == "Point"
    assert point_feat.measurement_status == MeasurementStatus.NOT_APPLICABLE.value


def test_ingest_shapefile_service(db_session: Session) -> None:
    coords = [[(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)]]
    zip_bytes = build_shapefile_zip(shapes=[coords])

    file_record = ingest_file(zip_bytes, "survey.zip", session=db_session)
    assert file_record.status == FileStatus.COMPLETED.value
    assert file_record.feature_count == 1

    repo = FileRepository(db_session)
    _, summary, _ = repo.get_file_measurements(file_record.id)
    assert summary["feature_count"] == 1
    assert summary["measured_count"] == 1
    assert summary["total_area_sq_m"] > 0


def test_ingest_invalid_file_marks_failed(db_session: Session) -> None:
    repo = FileRepository(db_session)

    with pytest.raises(InvalidFileError) as exc_info:
        ingest_file(b"<kml>broken xml", "broken.kml", session=db_session)

    file_id = exc_info.value.details.get("file_id")
    assert file_id is not None

    failed_file = repo.get_file(file_id)
    assert failed_file is not None
    assert failed_file.status == FileStatus.FAILED.value
    assert failed_file.error is not None


def test_ingest_unsupported_extension_creates_no_record(db_session: Session) -> None:
    repo = FileRepository(db_session)

    with pytest.raises(UnsupportedFormatError):
        ingest_file(b"data", "malicious.exe", session=db_session)

    _files, total = repo.list_files()
    assert total == 0
