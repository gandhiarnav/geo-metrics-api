"""Source CRS detection and labelling."""

from __future__ import annotations

from pyproj import CRS
from pyproj.exceptions import CRSError as PyprojCRSError

from app.core.errors import CRSError

WGS84 = CRS.from_epsg(4326)


def crs_from_prj(text: str) -> CRS:
    """Parse the WKT contained in a Shapefile ``.prj`` (OGC or ESRI flavour)."""
    text = text.strip()
    if not text:
        raise CRSError("The .prj file is empty")
    try:
        return CRS.from_user_input(text)
    except PyprojCRSError as exc:
        raise CRSError("The .prj file does not contain a valid CRS definition") from exc


def crs_label(crs: CRS) -> str:
    """Human-friendly CRS identifier: ``EPSG:xxxx`` when identifiable, else the CRS name."""
    epsg = crs.to_epsg(min_confidence=70)
    return f"EPSG:{epsg}" if epsg is not None else crs.name


def is_wgs84(crs: CRS) -> bool:
    return crs.equals(WGS84, ignore_axis_order=True)


def bounds_look_geographic(bounds: tuple[float, float, float, float]) -> bool:
    """True when coordinates *could* be longitude/latitude degrees."""
    min_x, min_y, max_x, max_y = bounds
    return -180.0 <= min_x <= max_x <= 180.0 and -90.0 <= min_y <= max_y <= 90.0
