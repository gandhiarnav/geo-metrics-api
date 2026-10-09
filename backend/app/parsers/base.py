"""Unified parser dispatch and format detection."""

from __future__ import annotations

import os

from app.core.config import Settings, get_settings
from app.core.errors import InvalidFileError, UnsupportedFormatError
from app.domain import ParsedFile
from app.parsers.kml import parse_kml_bytes, parse_kmz_bytes
from app.parsers.safe_zip import is_zip_bytes, read_safe_zip
from app.parsers.shapefile import parse_shapefile_zip_bytes

ALLOWED_EXTENSIONS = {".kml", ".kmz", ".zip"}


def parse_geospatial_file(
    data: bytes,
    filename: str,
    settings: Settings | None = None,
) -> ParsedFile:
    """Detect file format from extension and signature, dispatching to the appropriate parser."""
    settings = settings or get_settings()

    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        msg = f"Unsupported file format '{ext}'. Supported: .kml, .kmz, .zip (Shapefile archive)"
        raise UnsupportedFormatError(
            msg,
            details={"allowed_extensions": sorted(ALLOWED_EXTENSIONS), "filename": filename},
        )

    if not data or not data.strip():
        raise InvalidFileError(f"Uploaded file '{filename}' is empty")

    if ext == ".kml":
        if is_zip_bytes(data):
            raise InvalidFileError(
                "File has .kml extension but contains ZIP data (did you mean .kmz?)"
            )
        return parse_kml_bytes(data, settings)

    if ext == ".kmz":
        if not is_zip_bytes(data):
            raise InvalidFileError("File has .kmz extension but is not a valid ZIP archive")
        return parse_kmz_bytes(data, settings)

    # ext == ".zip"
    if not is_zip_bytes(data):
        raise InvalidFileError("File has .zip extension but is not a valid ZIP archive")

    # Inspect zip contents to distinguish Shapefile ZIP vs Zipped KML
    members = read_safe_zip(data, settings)
    has_shp = any(name.lower().endswith(".shp") for name in members)
    has_kml = any(name.lower().endswith(".kml") for name in members)

    if has_shp:
        return parse_shapefile_zip_bytes(data, settings)
    if has_kml:
        return parse_kmz_bytes(data, settings)

    raise InvalidFileError("ZIP archive contains neither a Shapefile (.shp) nor a KML (.kml) file")
