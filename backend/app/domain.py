"""Core domain types shared by parsers, the measurement engine and persistence.

These are plain dataclasses/enums: no FastAPI or database imports, so parsers and the
measurement engine can be unit-tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pyproj import CRS
from shapely.geometry.base import BaseGeometry


class FileType(StrEnum):
    KML = "kml"
    KMZ = "kmz"
    SHAPEFILE = "shapefile"


class FileStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MeasurementStatus(StrEnum):
    MEASURED = "MEASURED"
    """At least one area or length value was computed."""
    NOT_APPLICABLE = "NOT_APPLICABLE"
    """Geometry has no area or length by definition (points)."""
    UNSUPPORTED = "UNSUPPORTED"
    """Geometry kind the service does not know how to measure (e.g. gx:Track)."""
    ERROR = "ERROR"
    """Geometry is missing, empty or could not be transformed."""


@dataclass(frozen=True, slots=True)
class ParsedFeature:
    """A single feature extracted from an uploaded file, in the file's source CRS."""

    index: int
    geometry: BaseGeometry | None
    geometry_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    message: str | None = None
    """Parser-level note, e.g. why a geometry could not be read."""


@dataclass(frozen=True, slots=True)
class ParsedFile:
    file_type: FileType
    crs: CRS
    features: list[ParsedFeature]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Measurement:
    status: MeasurementStatus
    area_sq_m: float | None = None
    perimeter_m: float | None = None
    length_m: float | None = None
    geodesic_area_sq_m: float | None = None
    geodesic_length_m: float | None = None
    measurement_crs: str | None = None
    message: str | None = None
