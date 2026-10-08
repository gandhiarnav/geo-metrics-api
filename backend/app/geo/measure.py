"""Measurement engine.

Strategy
--------
1. Transform the feature from its source CRS to WGS84 longitude/latitude
   (``always_xy=True`` so axis order is always lon, lat).
2. Repair invalid polygons, normalise ring orientation and unwrap geometries that cross
   the antimeridian.
3. Project into a **Lambert Azimuthal Equal-Area** CRS centred on the feature itself.
   LAEA preserves area exactly and, close to its centre, distorts length negligibly,
   so there are no UTM zone boundaries, polar special cases or multi-zone features.
4. Measure with Shapely in metres, and compute an independent ellipsoidal (geodesic)
   reference with ``pyproj.Geod`` (Karney's algorithm). The two are compared and a
   note is attached when they diverge, which only happens for very large features.

Nothing here touches FastAPI or the database; it operates on Shapely geometries.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from functools import lru_cache

import numpy as np
import numpy.typing as npt
import shapely
from pyproj import CRS, Geod, Transformer
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry

from app.domain import Measurement, MeasurementStatus
from app.geo.crs import WGS84, is_wgs84

GEOD = Geod(ellps="WGS84")

#: Relative difference between projected and geodesic results above which a note is added.
DIVERGENCE_NOTE_THRESHOLD = 1e-3
#: Projection centres are rounded (~11 m) so the transformer cache is effective.
_CENTRE_DECIMALS = 4

CoordArray = npt.NDArray[np.float64]


def local_equal_area_crs(lon0: float, lat0: float) -> str:
    """PROJ definition of a LAEA projection centred on ``(lon0, lat0)``."""
    return (
        f"+proj=laea +lat_0={lat0} +lon_0={lon0} +x_0=0 +y_0=0 "
        "+datum=WGS84 +units=m +no_defs +type=crs"
    )


@lru_cache(maxsize=1024)
def _local_projector(lon0: float, lat0: float) -> Transformer:
    return Transformer.from_crs(WGS84, local_equal_area_crs(lon0, lat0), always_xy=True)


def _apply(transformer: Transformer, geometry: BaseGeometry) -> BaseGeometry:
    def _fn(coords: CoordArray) -> CoordArray:
        x, y = transformer.transform(coords[:, 0], coords[:, 1])
        return np.column_stack((x, y))

    return _transform_coords(geometry, _fn)


def _transform_coords(
    geometry: BaseGeometry, fn: Callable[[CoordArray], CoordArray]
) -> BaseGeometry:
    result: BaseGeometry = shapely.transform(geometry, fn)
    return result


def _atomic_parts(geometry: BaseGeometry) -> Iterator[BaseGeometry]:
    """Recursively flatten Multi* geometries and GeometryCollections."""
    if isinstance(geometry, BaseMultipartGeometry):
        for part in geometry.geoms:
            yield from _atomic_parts(part)
    elif not geometry.is_empty:
        yield geometry


def _unwrap_antimeridian(geometry: BaseGeometry) -> BaseGeometry:
    """Shift negative longitudes by +360° when a geometry spans more than 180°.

    A field straddling the 180° meridian is stored as e.g. ``179.9 … -179.9``; without
    unwrapping it would be measured as a band around the whole planet.
    """
    min_x, _, max_x, _ = geometry.bounds
    if max_x - min_x <= 180.0:
        return geometry

    def _shift(coords: CoordArray) -> CoordArray:
        lon = np.where(coords[:, 0] < 0.0, coords[:, 0] + 360.0, coords[:, 0])
        return np.column_stack((lon, coords[:, 1]))

    return _transform_coords(geometry, _shift)


def _merge_polygons(polygons: list[Polygon]) -> tuple[BaseGeometry | None, bool]:
    """Repair invalid polygons and dissolve overlaps so area is never double counted."""
    repaired = False
    cleaned: list[Polygon] = []
    for polygon in polygons:
        if polygon.is_valid:
            cleaned.append(polygon)
            continue
        repaired = True
        fixed = shapely.make_valid(polygon)
        cleaned.extend(p for p in _atomic_parts(fixed) if isinstance(p, Polygon))
    if not cleaned:
        return None, repaired
    merged = cleaned[0] if len(cleaned) == 1 else shapely.union_all(cleaned)
    # Counter-clockwise exteriors / clockwise holes: required for correct Geod signs.
    oriented: BaseGeometry = shapely.orient_polygons(merged)
    return oriented, repaired


def _relative_difference(value: float, reference: float) -> float:
    return abs(value - reference) / reference if reference > 0 else 0.0


class GeometryMeasurer:
    """Measures geometries expressed in one source CRS (instantiate once per file)."""

    def __init__(self, source_crs: CRS) -> None:
        self._to_wgs84: Transformer | None = (
            None
            if is_wgs84(source_crs)
            else Transformer.from_crs(source_crs, WGS84, always_xy=True)
        )

    def to_lonlat(self, geometry: BaseGeometry) -> BaseGeometry:
        """Return a 2D lon/lat copy of ``geometry``; raises ``ValueError`` if impossible."""
        geometry = shapely.force_2d(geometry)
        if self._to_wgs84 is not None:
            geometry = _apply(self._to_wgs84, geometry)
        coords = shapely.get_coordinates(geometry)
        if not np.isfinite(coords).all():
            raise ValueError("Coordinates could not be transformed to WGS84")
        if (np.abs(coords[:, 0]) > 180.0).any() or (np.abs(coords[:, 1]) > 90.0).any():
            raise ValueError("Coordinates fall outside the valid longitude/latitude range")
        return _unwrap_antimeridian(geometry)

    def measure(self, geometry: BaseGeometry | None) -> Measurement:
        if geometry is None or geometry.is_empty:
            return Measurement(MeasurementStatus.ERROR, message="Feature has no geometry")
        try:
            lonlat = self.to_lonlat(geometry)
        except ValueError as exc:
            return Measurement(MeasurementStatus.ERROR, message=str(exc))

        parts = list(_atomic_parts(lonlat))
        polygons = [p for p in parts if isinstance(p, Polygon)]
        lines = [p for p in parts if isinstance(p, LineString)]  # includes LinearRing
        has_points = any(isinstance(p, Point) for p in parts)

        if not polygons and not lines:
            if has_points:
                return Measurement(
                    MeasurementStatus.NOT_APPLICABLE,
                    message="Point geometries have no area or length",
                )
            return Measurement(
                MeasurementStatus.UNSUPPORTED,
                message=f"Geometry type {geometry.geom_type} cannot be measured",
            )

        notes: list[str] = []
        polygonal, repaired = _merge_polygons(polygons)
        if repaired:
            notes.append("Invalid polygon geometry was repaired before measurement")
        if has_points:
            notes.append("Point parts were ignored")
        linear: BaseGeometry | None = None
        if lines:
            linear = lines[0] if len(lines) == 1 else MultiLineString(lines)

        if polygonal is None and linear is None:
            return Measurement(
                MeasurementStatus.ERROR,
                message="Polygon geometry is degenerate and has no measurable area",
            )

        measured = [g for g in (polygonal, linear) if g is not None]
        min_x, min_y, max_x, max_y = shapely.GeometryCollection(measured).bounds
        lon0 = round(((min_x + max_x) / 2 + 180.0) % 360.0 - 180.0, _CENTRE_DECIMALS)
        lat0 = round((min_y + max_y) / 2, _CENTRE_DECIMALS)
        projector = _local_projector(lon0, lat0)

        area = perimeter = length = geodesic_area = geodesic_length = None
        if polygonal is not None:
            projected = _apply(projector, polygonal)
            area, perimeter = projected.area, projected.length
            signed_area, _ = GEOD.geometry_area_perimeter(polygonal)
            geodesic_area = abs(signed_area)
            if _relative_difference(area, geodesic_area) > DIVERGENCE_NOTE_THRESHOLD:
                notes.append("Feature is large for a local projection; see geodesic_area_sq_m")
        if linear is not None:
            length = _apply(projector, linear).length
            geodesic_length = GEOD.geometry_length(linear)
            if _relative_difference(length, geodesic_length) > DIVERGENCE_NOTE_THRESHOLD:
                notes.append("Feature is large for a local projection; see geodesic_length_m")

        return Measurement(
            MeasurementStatus.MEASURED,
            area_sq_m=area,
            perimeter_m=perimeter,
            length_m=length,
            geodesic_area_sq_m=geodesic_area,
            geodesic_length_m=geodesic_length,
            measurement_crs=local_equal_area_crs(lon0, lat0).removesuffix(" +type=crs"),
            message="; ".join(notes) or None,
        )


def measure_geometry(geometry: BaseGeometry | None, source_crs: CRS = WGS84) -> Measurement:
    """Convenience wrapper for one-off measurements."""
    return GeometryMeasurer(source_crs).measure(geometry)
