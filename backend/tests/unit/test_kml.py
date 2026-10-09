from __future__ import annotations

import io
import zipfile

import pytest
from shapely.geometry import GeometryCollection, LineString, Point, Polygon

from app.core.errors import InvalidFileError, UnsafeXMLError
from app.domain import FileType
from app.parsers.base import parse_geospatial_file
from app.parsers.kml import parse_kml_bytes, parse_kmz_bytes

SAMPLE_KML = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Survey Area</name>
    <Folder>
      <name>Agricultural Plots</name>
      <Placemark>
        <name>Plot Alpha</name>
        <description>Main paddy field</description>
        <ExtendedData>
          <Data name="crop"><value>Rice</value></Data>
          <Data name="soil_ph"><value>6.5</value></Data>
        </ExtendedData>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                77.590,12.970,0 77.595,12.970,0 77.595,12.975,0 77.590,12.975,0 77.590,12.970,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
      <Placemark>
        <name>Plot Beta (with pond)</name>
        <ExtendedData>
          <SchemaData>
            <SimpleData name="status">Active</SimpleData>
          </SchemaData>
        </ExtendedData>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                77.600,12.980 77.604,12.980 77.604,12.984 77.600,12.984 77.600,12.980
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
          <innerBoundaryIs>
            <LinearRing>
              <coordinates>
                77.601,12.981 77.603,12.981 77.603,12.983 77.601,12.983 77.601,12.981
              </coordinates>
            </LinearRing>
          </innerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>
    <Placemark>
      <name>Access Road</name>
      <LineString>
        <coordinates>
          77.590,12.970,10.5
          77.592,12.972,11.0
          77.594,12.974,12.0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Weather Station</name>
      <Point>
        <coordinates>77.591,12.971,920</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""


def test_parse_sample_kml() -> None:
    parsed = parse_kml_bytes(SAMPLE_KML)

    assert parsed.file_type is FileType.KML
    assert len(parsed.features) == 4
    assert len(parsed.warnings) == 0

    # Feature 0: Polygon
    f0 = parsed.features[0]
    assert f0.index == 0
    assert f0.geometry_type == "Polygon"
    assert isinstance(f0.geometry, Polygon)
    assert f0.properties["name"] == "Plot Alpha"
    assert f0.properties["crop"] == "Rice"
    assert f0.properties["soil_ph"] == "6.5"
    assert f0.properties["folder"] == "Survey Area/Agricultural Plots"

    # Feature 1: Polygon with hole
    f1 = parsed.features[1]
    assert f1.geometry_type == "Polygon"
    assert isinstance(f1.geometry, Polygon)
    assert len(f1.geometry.interiors) == 1
    assert f1.properties["status"] == "Active"

    # Feature 2: LineString
    f2 = parsed.features[2]
    assert f2.geometry_type == "LineString"
    assert isinstance(f2.geometry, LineString)
    assert len(f2.geometry.coords) == 3

    # Feature 3: Point
    f3 = parsed.features[3]
    assert f3.geometry_type == "Point"
    assert isinstance(f3.geometry, Point)
    assert f3.geometry.x == pytest.approx(77.591)
    assert f3.geometry.y == pytest.approx(12.971)


def test_parse_multigeometry_kml() -> None:
    kml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Placemark>
        <name>Composite Feature</name>
        <MultiGeometry>
          <Point><coordinates>10,20</coordinates></Point>
          <LineString><coordinates>10,20 11,21</coordinates></LineString>
        </MultiGeometry>
      </Placemark>
    </kml>
    """
    parsed = parse_kml_bytes(kml)
    assert len(parsed.features) == 1
    f = parsed.features[0]
    assert f.geometry_type == "MultiGeometry"
    assert isinstance(f.geometry, GeometryCollection)
    assert len(f.geometry.geoms) == 2


def test_parse_unsupported_tag_handled_gracefully() -> None:
    kml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
      <Placemark>
        <name>Flight Track</name>
        <gx:Track>
          <when>2026-10-09T00:00:00Z</when>
          <gx:coord>77.5 12.9 100</gx:coord>
        </gx:Track>
      </Placemark>
    </kml>
    """
    parsed = parse_kml_bytes(kml)
    assert len(parsed.features) == 1
    f = parsed.features[0]
    assert f.geometry is None
    assert "Unsupported" in (f.message or "")


def test_kmz_archive_parsed_correctly() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("doc.kml", SAMPLE_KML)
    kmz_bytes = buf.getvalue()

    parsed = parse_kmz_bytes(kmz_bytes)
    assert parsed.file_type is FileType.KMZ
    assert len(parsed.features) == 4


def test_xxe_entity_expansion_rejected() -> None:
    malicious_kml = b"""<?xml version="1.0"?>
    <!DOCTYPE root [
      <!ENTITY test "ENTITY_EXPANSION">
    ]>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Placemark>
        <name>&test;</name>
        <Point><coordinates>0,0</coordinates></Point>
      </Placemark>
    </kml>
    """
    with pytest.raises((UnsafeXMLError, InvalidFileError)):
        parse_kml_bytes(malicious_kml)


def test_empty_kml_raises() -> None:
    with pytest.raises(InvalidFileError, match="empty"):
        parse_kml_bytes(b"")


def test_malformed_xml_raises() -> None:
    with pytest.raises(InvalidFileError, match="Malformed"):
        parse_kml_bytes(b"<kml><Placemark><unclosed></kml>")


def test_dispatch_via_parse_geospatial_file() -> None:
    parsed = parse_geospatial_file(SAMPLE_KML, "survey.kml")
    assert parsed.file_type is FileType.KML
    assert len(parsed.features) == 4
