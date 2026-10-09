from __future__ import annotations

import datetime
import io
import zipfile

import pytest
import shapefile
from pyproj import CRS
from shapely.geometry import Polygon

from app.core.errors import CRSError, InvalidFileError
from app.domain import FileType
from app.geo.crs import WGS84
from app.parsers.base import parse_geospatial_file
from app.parsers.shapefile import parse_shapefile_zip_bytes

WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)
UTM43N_PRJ = CRS.from_epsg(32643).to_wkt()


def build_shapefile_zip(
    stem: str = "survey",
    shapes: list[list[list[tuple[float, float]]]] | None = None,
    records: list[list[object]] | None = None,
    shape_type: int = shapefile.POLYGON,
    prj: str | None = WGS84_PRJ,
    include_dbf: bool = True,
    include_shx: bool = True,
    extra_files: dict[str, bytes] | None = None,
) -> bytes:
    """Helper to generate an in-memory Shapefile ZIP archive."""
    shp_buf = io.BytesIO()
    shx_buf = io.BytesIO()
    dbf_buf = io.BytesIO()

    with shapefile.Writer(shp=shp_buf, shx=shx_buf, dbf=dbf_buf, shapeType=shape_type) as w:
        w.field("NAME", "C", size=50)
        w.field("VALUE", "N", size=10, decimal=2)
        w.field("DATE", "D")

        if shapes and records:
            for shape_parts, rec in zip(shapes, records, strict=True):
                w.poly(shape_parts)
                w.record(*rec)
        elif shapes:
            for shape_parts in shapes:
                w.poly(shape_parts)
                w.record("Default", 1.0, datetime.date(2026, 1, 1))

    members: dict[str, bytes] = {f"{stem}.shp": shp_buf.getvalue()}
    if include_shx:
        members[f"{stem}.shx"] = shx_buf.getvalue()
    if include_dbf:
        members[f"{stem}.dbf"] = dbf_buf.getvalue()
    if prj is not None:
        members[f"{stem}.prj"] = prj.encode("utf-8")

    if extra_files:
        members.update(extra_files)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return zip_buf.getvalue()


def test_parse_valid_polygon_shapefile() -> None:
    coords1 = [[(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)]]
    coords2 = [[(77.60, 12.98), (77.605, 12.98), (77.605, 12.985), (77.60, 12.985), (77.60, 12.98)]]

    zip_bytes = build_shapefile_zip(
        shapes=[coords1, coords2],
        records=[
            ["Plot A", 10.5, datetime.date(2026, 5, 10)],
            ["Plot B", 20.0, datetime.date(2026, 5, 11)],
        ],
    )

    parsed = parse_shapefile_zip_bytes(zip_bytes)
    assert parsed.file_type is FileType.SHAPEFILE
    assert len(parsed.features) == 2
    assert len(parsed.warnings) == 0

    f0 = parsed.features[0]
    assert f0.index == 0
    assert f0.geometry_type == "Polygon"
    assert isinstance(f0.geometry, Polygon)
    assert f0.properties["NAME"] == "Plot A"
    assert f0.properties["VALUE"] == pytest.approx(10.5)
    assert f0.properties["DATE"] == "2026-05-10"

    f1 = parsed.features[1]
    assert f1.properties["NAME"] == "Plot B"


def test_shapefile_without_prj_but_geographic_coords_warns() -> None:
    coords = [[(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)]]
    zip_bytes = build_shapefile_zip(shapes=[coords], prj=None)

    parsed = parse_shapefile_zip_bytes(zip_bytes)
    assert len(parsed.features) == 1
    assert parsed.crs.equals(WGS84, ignore_axis_order=True)
    assert any("assumed EPSG:4326" in w for w in parsed.warnings)


def test_shapefile_without_prj_and_projected_coords_raises() -> None:
    coords = [
        [
            (500000, 1400000),
            (501000, 1400000),
            (501000, 1401000),
            (500000, 1401000),
            (500000, 1400000),
        ]
    ]
    zip_bytes = build_shapefile_zip(shapes=[coords], prj=None)

    with pytest.raises(CRSError, match="not geographic degrees"):
        parse_shapefile_zip_bytes(zip_bytes)


def test_missing_dbf_raises() -> None:
    coords = [[(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)]]
    zip_bytes = build_shapefile_zip(shapes=[coords], include_dbf=False)

    with pytest.raises(InvalidFileError, match=r"missing required \.dbf"):
        parse_shapefile_zip_bytes(zip_bytes)


def test_missing_shx_raises() -> None:
    coords = [[(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)]]
    zip_bytes = build_shapefile_zip(shapes=[coords], include_shx=False)

    with pytest.raises(InvalidFileError, match=r"missing required \.shx"):
        parse_shapefile_zip_bytes(zip_bytes)


def test_multiple_shapefiles_in_zip_raises() -> None:
    coords = [[(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)]]
    extra = {"layer2.shp": b"fake", "layer2.shx": b"fake", "layer2.dbf": b"fake"}
    zip_bytes = build_shapefile_zip(shapes=[coords], extra_files=extra)

    with pytest.raises(InvalidFileError, match="multiple shapefiles"):
        parse_shapefile_zip_bytes(zip_bytes)


def test_dispatch_via_parse_geospatial_file_zip() -> None:
    coords = [[(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)]]
    zip_bytes = build_shapefile_zip(shapes=[coords])
    parsed = parse_geospatial_file(zip_bytes, "survey.zip")
    assert parsed.file_type is FileType.SHAPEFILE
    assert len(parsed.features) == 1
