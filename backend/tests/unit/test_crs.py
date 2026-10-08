from __future__ import annotations

import pytest
from pyproj import CRS

from app.core.errors import CRSError
from app.geo.crs import bounds_look_geographic, crs_from_prj, crs_label, is_wgs84

ESRI_WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)


def test_esri_wgs84_prj_is_identified_as_epsg_4326() -> None:
    crs = crs_from_prj(ESRI_WGS84_PRJ)
    assert crs_label(crs) == "EPSG:4326"
    assert is_wgs84(crs)


def test_ogc_projected_prj_is_identified() -> None:
    crs = crs_from_prj(CRS.from_epsg(32643).to_wkt())
    assert crs_label(crs) == "EPSG:32643"
    assert not is_wgs84(crs)


@pytest.mark.parametrize("text", ["", "   ", "not a crs"])
def test_invalid_prj_raises(text: str) -> None:
    with pytest.raises(CRSError):
        crs_from_prj(text)


def test_custom_crs_without_epsg_falls_back_to_name() -> None:
    crs = CRS.from_proj4("+proj=laea +lat_0=10 +lon_0=10 +datum=WGS84 +units=m")
    assert not crs_label(crs).startswith("EPSG:")


@pytest.mark.parametrize(
    ("bounds", "expected"),
    [
        ((77.5, 12.9, 77.6, 13.0), True),
        ((-180, -90, 180, 90), True),
        ((500_000, 1_400_000, 501_000, 1_401_000), False),
        ((10, 95, 11, 96), False),
    ],
)
def test_bounds_look_geographic(bounds: tuple[float, float, float, float], expected: bool) -> None:
    assert bounds_look_geographic(bounds) is expected
