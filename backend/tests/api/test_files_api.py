from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session
from app.core.config import Settings
from app.db.base import Base
from app.main import create_app
from tests.unit.test_kml import SAMPLE_KML
from tests.unit.test_shapefile import build_shapefile_zip


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    settings = Settings(max_upload_bytes=10 * 1024 * 1024)
    app = create_app(settings)
    app.dependency_overrides[get_db_session] = _override_db

    return TestClient(app)


def test_upload_kml_success(client: TestClient) -> None:
    files = {"file": ("survey.kml", SAMPLE_KML, "application/vnd.google-earth.kml+xml")}
    response = client.post("/api/files/", files=files)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "survey.kml"
    assert data["file_type"] == "kml"
    assert data["crs"] == "EPSG:4326"
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 4
    assert data["warnings"] == []


def test_upload_shapefile_zip_success(client: TestClient) -> None:
    coords = [[(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)]]
    zip_bytes = build_shapefile_zip(shapes=[coords])

    files = {"file": ("survey.zip", zip_bytes, "application/zip")}
    response = client.post("/api/files/", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 1


def test_upload_unsupported_format_returns_415(client: TestClient) -> None:
    files = {"file": ("data.txt", b"plain text", "text/plain")}
    response = client.post("/api/files/", files=files)

    assert response.status_code == 415
    data = response.json()
    assert data["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_upload_oversized_file_returns_413() -> None:
    # 2 MB payload with 1 MB limit
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    settings = Settings(max_upload_bytes=1024 * 1024)
    app = create_app(settings)

    def _get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = _get_db

    custom_client = TestClient(app)
    large_payload = b"0" * (2 * 1024 * 1024)
    files = {"file": ("large.kml", large_payload, "application/octet-stream")}
    response = custom_client.post("/api/files/", files=files)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "UPLOAD_TOO_LARGE"


def test_upload_corrupt_file_returns_422(client: TestClient) -> None:
    files = {"file": ("corrupt.kml", b"<kml>broken", "application/xml")}
    response = client.post("/api/files/", files=files)

    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "INVALID_FILE"
    assert "file_id" in data["error"]["details"]


def test_get_file_metadata(client: TestClient) -> None:
    files = {"file": ("survey.kml", SAMPLE_KML, "application/xml")}
    upload_resp = client.post("/api/files/", files=files)
    file_id = upload_resp.json()["id"]

    resp = client.get(f"/api/files/{file_id}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == file_id
    assert data["filename"] == "survey.kml"


def test_get_file_not_found_returns_404(client: TestClient) -> None:
    resp = client.get("/api/files/nonexistent_id/")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_list_files_paginated(client: TestClient) -> None:
    files = {"file": ("survey.kml", SAMPLE_KML, "application/xml")}
    client.post("/api/files/", files=files)

    resp = client.get("/api/files/?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_get_file_measurements_and_sql_summary(client: TestClient) -> None:
    files = {"file": ("survey.kml", SAMPLE_KML, "application/xml")}
    upload_resp = client.post("/api/files/", files=files)
    file_id = upload_resp.json()["id"]

    # Request with pagination limit=1
    resp = client.get(f"/api/files/{file_id}/measurements/?limit=1&offset=0")
    assert resp.status_code == 200
    data = resp.json()

    assert data["file_id"] == file_id
    assert data["source_crs"] == "EPSG:4326"
    assert data["units"]["area"] == "sq_m"
    assert data["units"]["length"] == "m"

    # Whole-file SQL summary reflects all 4 features in file
    summary = data["summary"]
    assert summary["feature_count"] == 4
    assert summary["measured_count"] == 3
    assert summary["not_applicable_count"] == 1
    assert summary["total_area_sq_m"] > 0
    assert summary["total_length_m"] > 0

    # Paginated measurements list contains only 1 feature
    assert len(data["measurements"]) == 1
    f0 = data["measurements"][0]
    assert f0["feature_index"] == 0
    assert f0["geometry_type"] == "Polygon"
    assert f0["status"] == "MEASURED"
    assert f0["area_sq_m"] is not None


def test_get_file_features(client: TestClient) -> None:
    files = {"file": ("survey.kml", SAMPLE_KML, "application/xml")}
    upload_resp = client.post("/api/files/", files=files)
    file_id = upload_resp.json()["id"]

    resp = client.get(f"/api/files/{file_id}/features/?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert len(data["features"]) == 2

    f0 = data["features"][0]
    assert f0["feature_index"] == 0
    assert f0["geometry_type"] == "Polygon"
    assert f0["geometry"]["type"] == "Polygon"
    assert f0["properties"]["name"] == "Plot Alpha"
    assert f0["properties"]["crop"] == "Rice"
