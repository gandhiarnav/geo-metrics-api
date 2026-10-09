"""Deterministic sample geospatial data generator for demonstration and evaluation."""

from __future__ import annotations

import datetime
import io
import os
import zipfile

import shapefile

SAMPLE_KML_TEXT = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Karnataka Drone Survey</name>
    <description>Agricultural and infrastructure boundary survey near Bengaluru</description>
    <Folder>
      <name>Parcels</name>
      <Placemark>
        <name>Plot Alpha - Agricultural Field</name>
        <description>Rice paddy field with perimeter irrigation</description>
        <ExtendedData>
          <Data name="crop_type"><value>Paddy Rice</value></Data>
          <Data name="irrigation"><value>Canal</value></Data>
          <Data name="soil_type"><value>Red Loam</value></Data>
        </ExtendedData>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                77.5900,12.9700,0
                77.5950,12.9700,0
                77.5950,12.9750,0
                77.5900,12.9750,0
                77.5900,12.9700,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
      <Placemark>
        <name>Plot Beta - Storage Reservoir with Island</name>
        <description>Water storage reservoir containing a central ecological island</description>
        <ExtendedData>
          <SchemaData>
            <SimpleData name="facility_id">RES-402</SimpleData>
            <SimpleData name="status">Active</SimpleData>
          </SchemaData>
        </ExtendedData>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                77.6000,12.9800,0
                77.6040,12.9800,0
                77.6040,12.9840,0
                77.6000,12.9840,0
                77.6000,12.9800,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
          <innerBoundaryIs>
            <LinearRing>
              <coordinates>
                77.6010,12.9810,0
                77.6030,12.9810,0
                77.6030,12.9830,0
                77.6010,12.9830,0
                77.6010,12.9810,0
              </coordinates>
            </LinearRing>
          </innerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>
    <Folder>
      <name>Infrastructure</name>
      <Placemark>
        <name>Primary Drainage Canal</name>
        <description>Concrete-lined water transfer channel</description>
        <ExtendedData>
          <Data name="capacity_m3_s"><value>12.5</value></Data>
        </ExtendedData>
        <LineString>
          <coordinates>
            77.5900,12.9700,910
            77.5925,12.9720,908
            77.5950,12.9740,905
            77.6000,12.9760,902
          </coordinates>
        </LineString>
      </Placemark>
      <Placemark>
        <name>Secondary Access Road</name>
        <description>Unpaved farm access road</description>
        <LineString>
          <coordinates>
            77.6000,12.9800,900
            77.6020,12.9820,901
            77.6040,12.9840,903
          </coordinates>
        </LineString>
      </Placemark>
      <Placemark>
        <name>Weather Monitoring Station</name>
        <description>Automated telemetry sensor mast</description>
        <Point>
          <coordinates>77.5925,12.9725,915</coordinates>
        </Point>
      </Placemark>
    </Folder>
  </Document>
</kml>
"""

WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)


def generate_shapefile_zip(output_path: str) -> None:
    shp_buf = io.BytesIO()
    shx_buf = io.BytesIO()
    dbf_buf = io.BytesIO()

    with shapefile.Writer(shp=shp_buf, shx=shx_buf, dbf=dbf_buf, shapeType=shapefile.POLYGON) as w:
        w.field("PLOT_ID", "C", size=16)
        w.field("CROP", "C", size=32)
        w.field("EST_HA", "N", size=10, decimal=2)
        w.field("SURV_DATE", "D")

        # Parcel 1
        p1 = [
            [
                (77.590, 12.970),
                (77.595, 12.970),
                (77.595, 12.975),
                (77.590, 12.975),
                (77.590, 12.970),
            ]
        ]
        w.poly(p1)
        w.record("P-001", "Paddy Rice", 30.04, datetime.date(2026, 10, 1))

        # Parcel 2
        p2 = [
            [
                (77.600, 12.980),
                (77.604, 12.980),
                (77.604, 12.984),
                (77.600, 12.984),
                (77.600, 12.980),
            ]
        ]
        w.poly(p2)
        w.record("P-002", "Maize", 19.23, datetime.date(2026, 10, 2))

        # Parcel 3
        p3 = [
            [
                (77.605, 12.985),
                (77.609, 12.985),
                (77.609, 12.988),
                (77.605, 12.988),
                (77.605, 12.985),
            ]
        ]
        w.poly(p3)
        w.record("P-003", "Pulses", 15.02, datetime.date(2026, 10, 3))

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("parcels.shp", shp_buf.getvalue())
        zf.writestr("parcels.shx", shx_buf.getvalue())
        zf.writestr("parcels.dbf", dbf_buf.getvalue())
        zf.writestr("parcels.prj", WGS84_PRJ)
        zf.writestr("parcels.cpg", "UTF-8\n")


def generate_kmz(output_path: str) -> None:
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", SAMPLE_KML_TEXT.strip())


def main() -> None:
    samples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "samples"))
    os.makedirs(samples_dir, exist_ok=True)

    kml_path = os.path.join(samples_dir, "survey.kml")
    with open(kml_path, "w", encoding="utf-8") as f:
        f.write(SAMPLE_KML_TEXT.strip())
    print(f"Generated {kml_path}")

    kmz_path = os.path.join(samples_dir, "survey.kmz")
    generate_kmz(kmz_path)
    print(f"Generated {kmz_path}")

    shp_path = os.path.join(samples_dir, "survey_shapefile.zip")
    generate_shapefile_zip(shp_path)
    print(f"Generated {shp_path}")


if __name__ == "__main__":
    main()
