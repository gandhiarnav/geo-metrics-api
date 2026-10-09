"""Zipped Shapefile parser.

Inspects a ZIP archive for Shapefile components (.shp, .shx, .dbf, .prj, .cpg),
validates single-layer requirement, extracts geometries via pyshp, resolves CRS,
and sanitizes attribute records into JSON-serializable properties.
"""

from __future__ import annotations

import datetime
import io
from typing import Any

import shapefile
from pyproj import CRS
from shapely.geometry import shape as shapely_shape
from shapely.geometry.base import BaseGeometry

from app.core.config import Settings, get_settings
from app.core.errors import CRSError, InvalidFileError
from app.domain import FileType, ParsedFeature, ParsedFile
from app.geo.crs import WGS84, bounds_look_geographic, crs_from_prj
from app.parsers.safe_zip import read_safe_zip


def _find_matching_companion(
    members: dict[str, bytes], stem_lower: str, extension_lower: str
) -> str | None:
    """Find member filename matching the stem and extension case-insensitively."""
    target = f"{stem_lower}.{extension_lower}"
    for name in members:
        if name.lower() == target:
            return name
    return None


def _sanitize_record_value(val: Any) -> Any:
    """Ensure DBF attribute values are JSON-serializable."""
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def parse_shapefile_zip_bytes(data: bytes, settings: Settings | None = None) -> ParsedFile:
    """Safely unpack and parse a zipped Shapefile from memory."""
    settings = settings or get_settings()

    members = read_safe_zip(data, settings)

    # Find all .shp files
    shp_members = [name for name in members if name.lower().endswith(".shp")]
    if not shp_members:
        raise InvalidFileError("ZIP archive contains no .shp file")
    if len(shp_members) > 1:
        count = len(shp_members)
        raise InvalidFileError(
            f"ZIP archive contains multiple shapefiles ({count} found); single-layer only"
        )

    shp_name = shp_members[0]
    stem = shp_name[:-4]
    stem_lower = stem.lower()

    # Locate companions
    shx_name = _find_matching_companion(members, stem_lower, "shx")
    dbf_name = _find_matching_companion(members, stem_lower, "dbf")
    prj_name = _find_matching_companion(members, stem_lower, "prj")
    cpg_name = _find_matching_companion(members, stem_lower, "cpg")

    if dbf_name is None:
        raise InvalidFileError(f"Shapefile '{shp_name}' is missing required .dbf attribute file")
    if shx_name is None:
        raise InvalidFileError(f"Shapefile '{shp_name}' is missing required .shx index file")

    # Determine encoding from .cpg if present
    encoding = "utf-8"
    if cpg_name is not None:
        raw_cpg = members[cpg_name].decode("utf-8", errors="ignore").strip()
        if raw_cpg:
            encoding = raw_cpg

    # Read shapefile in-memory
    try:
        reader = shapefile.Reader(
            shp=io.BytesIO(members[shp_name]),
            shx=io.BytesIO(members[shx_name]),
            dbf=io.BytesIO(members[dbf_name]),
            encoding=encoding,
            encodingErrors="replace",
        )
    except Exception as exc:
        raise InvalidFileError(f"Failed to read Shapefile data: {exc}") from exc

    features: list[ParsedFeature] = []
    warnings: list[str] = []

    try:
        shape_records = reader.shapeRecords()
    except Exception as exc:
        raise InvalidFileError(f"Corrupted Shapefile records: {exc}") from exc

    # Extract geometries and properties
    for idx, sr in enumerate(shape_records):
        if idx >= settings.max_features:
            if len(warnings) < settings.max_warnings:
                limit = settings.max_features
                warnings.append(f"Reached feature limit of {limit}; further features omitted")
            break

        # Convert record to dict
        props: dict[str, Any] = {}
        try:
            raw_props = sr.record.as_dict()
            props = {k: _sanitize_record_value(v) for k, v in raw_props.items()}
        except Exception:
            props = {}

        # Geometry
        geom: BaseGeometry | None = None
        geom_type = "None"
        msg: str | None = None

        if sr.shape.shapeType == shapefile.NULL:
            geom_type = "NullShape"
            msg = "Shapefile record has NULL geometry"
        else:
            try:
                geom_dict = sr.shape.__geo_interface__
                geom_type = geom_dict.get("type", "Unknown")
                geom = shapely_shape(geom_dict)
                if geom.is_empty:
                    geom = None
                    msg = "Shapefile record geometry is empty"
            except Exception as exc:
                geom_type = "Error"
                msg = f"Failed to construct geometry: {exc}"

        features.append(
            ParsedFeature(
                index=idx,
                geometry=geom,
                geometry_type=geom_type,
                properties=props,
                message=msg,
            )
        )

    # Resolve CRS
    resolved_crs: CRS
    if prj_name is not None:
        prj_text = members[prj_name].decode("utf-8", errors="replace")
        resolved_crs = crs_from_prj(prj_text)
    else:
        # Check coordinates bounds
        bbox = reader.bbox
        if bbox and len(bbox) == 4 and bounds_look_geographic(tuple(bbox)):
            resolved_crs = WGS84
            warnings.append("No .prj file found; assumed EPSG:4326 based on coordinate range")
        else:
            raise CRSError("Shapefile has no .prj file and coordinates are not geographic degrees")

    if not features:
        warnings.append("Shapefile contains no records")

    return ParsedFile(
        file_type=FileType.SHAPEFILE,
        crs=resolved_crs,
        features=features,
        warnings=warnings,
    )
