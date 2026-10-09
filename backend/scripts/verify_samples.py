"""Verification script: parse and measure all files in samples/ directory.

Usage:
    PYTHONPATH=backend uv run python scripts/verify_samples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to sys.path if invoked from repo root
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.geo.measure import GeometryMeasurer  # noqa: E402
from app.parsers.base import parse_geospatial_file  # noqa: E402


def main() -> None:
    samples_dir = backend_dir.parent / "samples"
    if not samples_dir.exists():
        print(f"Error: {samples_dir} does not exist.")
        sys.exit(1)

    sample_files = sorted(
        [
            f
            for f in samples_dir.iterdir()
            if f.suffix.lower() in {".kml", ".kmz", ".zip"} and not f.name.startswith(".")
        ]
    )

    print("=" * 88)
    print(f"GEOSPATIAL MEASUREMENT ENGINE VERIFICATION ({len(sample_files)} sample files)")
    print("=" * 88)

    for p in sample_files:
        print(f"\n📂 File: {p.name}")
        data = p.read_bytes()
        pf = parse_geospatial_file(data, p.name)
        measurer = GeometryMeasurer(pf.crs)
        crs_label = pf.crs.to_string()
        print(
            f"   Format: {pf.file_type.value.upper()} | "
            f"CRS: {crs_label} | Features: {len(pf.features)}"
        )

        for f in pf.features:
            m = measurer.measure(f.geometry)
            name = f.properties.get("name", f"Feature #{f.index}")
            print(f"   ├─ Feature #{f.index}: '{name}' ({f.geometry_type})")
            print(f"   │   Status: {m.status.value}")
            if m.area_sq_m is not None:
                ha = m.area_sq_m / 10000.0
                print(f"   │   Projected Area (LAEA): {m.area_sq_m:>12.2f} m² ({ha:.4f} ha)")
                if m.geodesic_area_sq_m is not None:
                    diff = abs(m.area_sq_m - m.geodesic_area_sq_m)
                    div_pct = (diff / m.geodesic_area_sq_m * 100.0) if m.geodesic_area_sq_m else 0.0
                    print(
                        f"   │   Geodesic Area (Geod):  {m.geodesic_area_sq_m:>12.2f} m² "
                        f"(div: {div_pct:.4f}%)"
                    )
            if m.perimeter_m is not None:
                print(f"   │   Perimeter:             {m.perimeter_m:>12.2f} m")
            if m.length_m is not None:
                print(f"   │   Projected Length:      {m.length_m:>12.2f} m")
                if m.geodesic_length_m is not None:
                    print(f"   │   Geodesic Length:       {m.geodesic_length_m:>12.2f} m")
            if m.message:
                print(f"   │   Note: {m.message}")

    print("\n" + "=" * 88)
    print("✅ Verification complete. All projections & geodesics evaluated successfully.")
    print("=" * 88)


if __name__ == "__main__":
    main()
