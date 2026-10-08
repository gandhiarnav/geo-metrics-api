"""Accuracy and behaviour tests for the measurement engine.

``pyproj.Geod`` (Karney's ellipsoidal algorithm) is the oracle: projected results must
agree with it to within 0.01 %.
"""

from __future__ import annotations

import pytest
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from app.domain import MeasurementStatus
from app.geo.measure import GEOD, measure_geometry

TOLERANCE = 1e-4  # 0.01 %


def reproject(geometry, transformer: Transformer):  # type: ignore[no-untyped-def]
    return shapely.transform(geometry, transformer.transform, interleaved=False)


def square(lon: float, lat: float, size_deg: float = 0.01) -> Polygon:
    return Polygon(
        [(lon, lat), (lon + size_deg, lat), (lon + size_deg, lat + size_deg), (lon, lat + size_deg)]
    )


def geodesic_area(polygon: Polygon) -> float:
    oriented = Polygon(
        LinearRing(polygon.exterior.coords[::-1])
        if polygon.exterior.is_ccw is False
        else polygon.exterior,
        [
            LinearRing(r.coords) if not r.is_ccw else LinearRing(r.coords[::-1])
            for r in polygon.interiors
        ],
    )
    return abs(GEOD.geometry_area_perimeter(oriented)[0])


@pytest.mark.parametrize("lat", [0.0, 12.97, 45.0, 60.0, 78.0, -33.9, -85.0])
def test_polygon_area_matches_geodesic_at_any_latitude(lat: float) -> None:
    polygon = square(77.59, lat)
    result = measure_geometry(polygon)

    assert result.status is MeasurementStatus.MEASURED
    assert result.area_sq_m == pytest.approx(geodesic_area(polygon), rel=TOLERANCE)
    assert result.area_sq_m == pytest.approx(result.geodesic_area_sq_m, rel=TOLERANCE)
    assert result.length_m is None
    assert result.perimeter_m is not None
    assert result.measurement_crs is not None
    assert result.measurement_crs.startswith("+proj=laea")


def test_area_is_metres_not_degrees() -> None:
    # 0.005° x 0.005° near Bengaluru is roughly 542 m x 553 m.
    result = measure_geometry(square(77.59, 12.97, 0.005))
    assert result.area_sq_m == pytest.approx(300_000, rel=0.01)


def test_polygon_hole_is_subtracted() -> None:
    outer = square(77.6, 12.98, 0.004).exterior
    hole = square(77.601, 12.981, 0.002).exterior
    with_hole = Polygon(outer, [hole])

    result = measure_geometry(with_hole)

    expected = (
        measure_geometry(Polygon(outer)).area_sq_m - measure_geometry(Polygon(hole)).area_sq_m
    )
    assert result.area_sq_m == pytest.approx(expected, rel=TOLERANCE)
    assert result.geodesic_area_sq_m == pytest.approx(expected, rel=TOLERANCE)


def test_hole_with_same_winding_as_shell_is_still_subtracted() -> None:
    outer = square(77.6, 12.98, 0.004)
    hole_same_winding = square(77.601, 12.981, 0.002)
    polygon = Polygon(outer.exterior.coords, [hole_same_winding.exterior.coords])

    result = measure_geometry(polygon)

    assert result.geodesic_area_sq_m == pytest.approx(result.area_sq_m, rel=TOLERANCE)
    assert result.area_sq_m < measure_geometry(outer).area_sq_m


def test_multipolygon_area_is_sum_of_parts() -> None:
    a, b = square(10.0, 50.0), square(10.1, 50.1)
    result = measure_geometry(MultiPolygon([a, b]))
    expected = measure_geometry(a).area_sq_m + measure_geometry(b).area_sq_m
    assert result.area_sq_m == pytest.approx(expected, rel=TOLERANCE)


def test_self_intersecting_polygon_is_repaired_and_measured() -> None:
    bowtie = Polygon([(0, 0), (0.01, 0.01), (0.01, 0), (0, 0.01)])
    result = measure_geometry(bowtie)

    assert result.status is MeasurementStatus.MEASURED
    # Two triangles, each a quarter of the 0.01° square.
    assert result.area_sq_m == pytest.approx(measure_geometry(square(0, 0)).area_sq_m / 2, rel=1e-3)
    assert result.message is not None
    assert "repaired" in result.message


@pytest.mark.parametrize(
    "line",
    [
        LineString([(0, 0), (0.01, 0)]),
        LineString([(77.59, 12.97), (77.60, 12.98), (77.61, 12.975)]),
        LineString([(-70.0, 60.0), (-70.0, 60.05)]),
    ],
)
def test_line_length_matches_geodesic(line: LineString) -> None:
    result = measure_geometry(line)
    assert result.status is MeasurementStatus.MEASURED
    assert result.length_m == pytest.approx(GEOD.geometry_length(line), rel=TOLERANCE)
    assert result.area_sq_m is None


def test_one_hundredth_degree_of_equator_is_about_1113_metres() -> None:
    result = measure_geometry(LineString([(0, 0), (0.01, 0)]))
    assert result.length_m == pytest.approx(1113.19, abs=0.05)


def test_multilinestring_length_is_sum_of_parts() -> None:
    a = LineString([(0, 0), (0.01, 0)])
    b = LineString([(1, 1), (1, 1.01)])
    result = measure_geometry(MultiLineString([a, b]))
    expected = GEOD.geometry_length(a) + GEOD.geometry_length(b)
    assert result.length_m == pytest.approx(expected, rel=TOLERANCE)


def test_linear_ring_is_measured_as_length() -> None:
    ring = LinearRing(square(5, 5).exterior.coords)
    result = measure_geometry(ring)
    assert result.length_m is not None
    assert result.area_sq_m is None


@pytest.mark.parametrize("geometry", [Point(1, 1), MultiPoint([(1, 1), (2, 2)])])
def test_points_are_not_applicable(geometry: Point | MultiPoint) -> None:
    result = measure_geometry(geometry)
    assert result.status is MeasurementStatus.NOT_APPLICABLE
    assert result.area_sq_m is None
    assert result.length_m is None


@pytest.mark.parametrize("geometry", [None, Polygon(), GeometryCollection()])
def test_missing_or_empty_geometry_is_an_error(geometry: Polygon | None) -> None:
    assert measure_geometry(geometry).status is MeasurementStatus.ERROR


def test_out_of_range_coordinates_are_an_error() -> None:
    result = measure_geometry(LineString([(0, 0), (0, 95)]))
    assert result.status is MeasurementStatus.ERROR


def test_mixed_collection_measures_area_and_length_and_ignores_points() -> None:
    polygon = square(20, 20)
    line = LineString([(20, 20), (20.01, 20)])
    result = measure_geometry(GeometryCollection([polygon, line, Point(20, 20)]))

    assert result.status is MeasurementStatus.MEASURED
    assert result.area_sq_m == pytest.approx(measure_geometry(polygon).area_sq_m, rel=TOLERANCE)
    assert result.length_m == pytest.approx(GEOD.geometry_length(line), rel=TOLERANCE)
    assert result.message is not None
    assert "Point parts were ignored" in result.message


def test_overlapping_polygons_in_collection_are_not_double_counted() -> None:
    a = square(0, 0, 0.01)
    result = measure_geometry(GeometryCollection([a, a]))
    assert result.area_sq_m == pytest.approx(measure_geometry(a).area_sq_m, rel=TOLERANCE)


def test_polygon_crossing_antimeridian_is_measured_as_a_small_area() -> None:
    crossing = Polygon([(179.995, 0), (-179.995, 0), (-179.995, 0.01), (179.995, 0.01)])
    unwrapped = Polygon([(179.995, 0), (180.005, 0), (180.005, 0.01), (179.995, 0.01)])

    result = measure_geometry(crossing)

    assert result.area_sq_m == pytest.approx(measure_geometry(square(0, 0)).area_sq_m, rel=1e-3)
    assert result.geodesic_area_sq_m == pytest.approx(geodesic_area(unwrapped), rel=TOLERANCE)


def test_z_coordinates_are_ignored() -> None:
    flat = square(30, 30)
    with_z = Polygon([(x, y, 1500.0) for x, y in flat.exterior.coords])
    assert measure_geometry(with_z).area_sq_m == pytest.approx(
        measure_geometry(flat).area_sq_m, rel=1e-12
    )


# --- Projected source CRSs -------------------------------------------------------------


def test_web_mercator_input_is_reprojected_not_measured_natively() -> None:
    # A 1 km x 1 km square *in Web Mercator units* at 60°N covers only ~0.25 km² on the ground.
    to_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x, y = to_3857.transform(10.0, 60.0)
    polygon = Polygon([(x, y), (x + 1000, y), (x + 1000, y + 1000), (x, y + 1000)])

    result = measure_geometry(polygon, CRS.from_epsg(3857))

    assert polygon.area == pytest.approx(1_000_000)
    assert result.area_sq_m == pytest.approx(250_000, rel=0.01)
    assert result.area_sq_m == pytest.approx(result.geodesic_area_sq_m, rel=TOLERANCE)


def test_utm_input_round_trips_through_wgs84() -> None:
    utm = CRS.from_epsg(32643)
    to_utm = Transformer.from_crs("EPSG:4326", utm, always_xy=True)
    polygon_ll = square(77.59, 12.97)
    polygon_utm = reproject(polygon_ll, to_utm)

    result = measure_geometry(polygon_utm, utm)

    assert result.area_sq_m == pytest.approx(geodesic_area(polygon_ll), rel=TOLERANCE)


def test_projected_input_in_us_feet_is_converted() -> None:
    # NAD83 / California zone 6 (ftUS); a line of 3280.833 ftUS is 1000 m on the grid.
    crs = CRS.from_epsg(2230)
    to_ll = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    line = LineString([(6_300_000, 1_900_000), (6_300_000 + 3280.833, 1_900_000)])

    result = measure_geometry(line, crs)

    assert result.length_m == pytest.approx(1000, rel=1e-3)
    assert result.length_m == pytest.approx(
        GEOD.geometry_length(reproject(line, to_ll)), rel=TOLERANCE
    )


def test_large_feature_gets_divergence_note() -> None:
    continent_sized = square(0, 0, 40)
    result = measure_geometry(continent_sized)
    assert result.status is MeasurementStatus.MEASURED
    assert result.message is not None
    assert "large for a local projection" in result.message
