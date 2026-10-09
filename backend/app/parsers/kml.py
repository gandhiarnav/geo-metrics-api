"""Hardened, namespace-agnostic KML and KMZ parser.

Extracts Placemarks from KML 2.0 / 2.1 / 2.2 / 2.3 documents, converting geometries into
Shapely objects, preserving folder hierarchy, names, descriptions, and ExtendedData.

Security:
- Hardened lxml XMLParser preventing XXE (XML External Entity), entity expansion bombs
  (Billion Laughs), and network access.
- Safe in-memory decompression for KMZ archives via safe_zip.
"""

from __future__ import annotations

import re
from typing import Any

from lxml import etree
from shapely.geometry import GeometryCollection, LinearRing, LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from app.core.config import Settings, get_settings
from app.core.errors import InvalidFileError, UnsafeXMLError
from app.domain import FileType, ParsedFeature, ParsedFile
from app.geo.crs import WGS84
from app.parsers.safe_zip import read_safe_zip


def _local_name(elem: etree._Element) -> str:
    """Return XML tag without namespace."""
    tag = elem.tag
    if not isinstance(tag, str):
        return ""
    return tag.split("}")[-1] if "}" in tag else tag


def _find_direct_child(elem: etree._Element, tag_name: str) -> etree._Element | None:
    for child in elem:
        if _local_name(child) == tag_name:
            return child
    return None


def _find_direct_children(elem: etree._Element, tag_name: str) -> list[etree._Element]:
    return [child for child in elem if _local_name(child) == tag_name]


def _parse_coordinates(coord_str: str) -> list[tuple[float, float]]:
    """Parse coordinate string formatted as 'lon,lat[,alt]' separated by whitespace."""
    points: list[tuple[float, float]] = []
    # KML coordinates can have whitespace between coordinates or newlines
    tokens = re.split(r"[\s\r\n\t]+", coord_str.strip())
    for token in tokens:
        if not token:
            continue
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                points.append((lon, lat))
            except ValueError:
                continue
    return points


def _parse_geometry_element(elem: etree._Element) -> tuple[BaseGeometry | None, str, str | None]:
    """Parse a single KML geometry XML element into a Shapely geometry.

    Returns (geometry, geometry_type, message).
    """
    tag = _local_name(elem)

    if tag == "Point":
        coord_elem = _find_direct_child(elem, "coordinates")
        if coord_elem is not None and coord_elem.text:
            coords = _parse_coordinates(coord_elem.text)
            if coords:
                return Point(coords[0]), "Point", None
        return None, "Point", "Point has missing or invalid coordinates"

    if tag == "LineString":
        coord_elem = _find_direct_child(elem, "coordinates")
        if coord_elem is not None and coord_elem.text:
            coords = _parse_coordinates(coord_elem.text)
            if len(coords) >= 2:
                return LineString(coords), "LineString", None
            if len(coords) == 1:
                return (
                    Point(coords[0]),
                    "Point",
                    "LineString contained only 1 point; converted to Point",
                )
        return None, "LineString", "LineString has fewer than 2 valid coordinates"

    if tag == "LinearRing":
        coord_elem = _find_direct_child(elem, "coordinates")
        if coord_elem is not None and coord_elem.text:
            coords = _parse_coordinates(coord_elem.text)
            if len(coords) >= 3:
                # Ensure closed
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                return LinearRing(coords), "LinearRing", None
        return None, "LinearRing", "LinearRing has fewer than 3 valid coordinates"

    if tag == "Polygon":
        outer_elem = _find_direct_child(elem, "outerBoundaryIs")
        if outer_elem is None:
            return None, "Polygon", "Polygon is missing outerBoundaryIs"
        outer_ring_elem = _find_direct_child(outer_elem, "LinearRing")
        if outer_ring_elem is None:
            return None, "Polygon", "Polygon outerBoundaryIs is missing LinearRing"
        outer_coord_elem = _find_direct_child(outer_ring_elem, "coordinates")
        if outer_coord_elem is None or not outer_coord_elem.text:
            return None, "Polygon", "Polygon outerBoundaryIs LinearRing has no coordinates"

        outer_coords = _parse_coordinates(outer_coord_elem.text)
        if len(outer_coords) < 3:
            return None, "Polygon", "Polygon outer boundary requires at least 3 points"
        if outer_coords[0] != outer_coords[-1]:
            outer_coords.append(outer_coords[0])

        inner_rings: list[list[tuple[float, float]]] = []
        for inner_elem in _find_direct_children(elem, "innerBoundaryIs"):
            inner_ring_elem = _find_direct_child(inner_elem, "LinearRing")
            if inner_ring_elem is not None:
                inner_coord_elem = _find_direct_child(inner_ring_elem, "coordinates")
                if inner_coord_elem is not None and inner_coord_elem.text:
                    inner_coords = _parse_coordinates(inner_coord_elem.text)
                    if len(inner_coords) >= 3:
                        if inner_coords[0] != inner_coords[-1]:
                            inner_coords.append(inner_coords[0])
                        inner_rings.append(inner_coords)

        try:
            poly = Polygon(outer_coords, inner_rings)
            return poly, "Polygon", None
        except Exception as exc:
            return None, "Polygon", f"Invalid polygon construction: {exc}"

    if tag == "MultiGeometry":
        sub_geoms: list[BaseGeometry] = []
        messages: list[str] = []
        for child in elem:
            sub_geom, _, sub_msg = _parse_geometry_element(child)
            if sub_geom is not None and not sub_geom.is_empty:
                sub_geoms.append(sub_geom)
            elif sub_msg:
                messages.append(sub_msg)

        if sub_geoms:
            geom_col = GeometryCollection(sub_geoms)
            msg = "; ".join(messages) if messages else None
            return geom_col, "MultiGeometry", msg
        return None, "MultiGeometry", "MultiGeometry contained no valid child geometries"

    # Known unsupported geometry tags
    known_unsupported = {"Track", "MultiTrack", "Model"}
    if tag in known_unsupported or tag.startswith("gx:"):
        return None, tag, f"Unsupported KML geometry element: {tag}"

    return None, tag, f"Unrecognized KML geometry element: {tag}"


def _extract_placemark_properties(placemark: etree._Element, folder_path: str) -> dict[str, Any]:
    """Extract metadata, ExtendedData, and folder path attributes."""
    props: dict[str, Any] = {}
    if folder_path:
        props["folder"] = folder_path

    name_elem = _find_direct_child(placemark, "name")
    if name_elem is not None and name_elem.text:
        props["name"] = name_elem.text.strip()

    desc_elem = _find_direct_child(placemark, "description")
    if desc_elem is not None and desc_elem.text:
        props["description"] = desc_elem.text.strip()

    # ExtendedData
    ext_data = _find_direct_child(placemark, "ExtendedData")
    if ext_data is not None:
        # 1. <Data name="foo"><value>bar</value></Data>
        for data_elem in _find_direct_children(ext_data, "Data"):
            key = data_elem.get("name")
            if key:
                val_elem = _find_direct_child(data_elem, "value")
                props[key] = val_elem.text.strip() if val_elem is not None and val_elem.text else ""

        # 2. <SchemaData><SimpleData name="foo">bar</SimpleData></SchemaData>
        for schema_data in _find_direct_children(ext_data, "SchemaData"):
            for simple_data in _find_direct_children(schema_data, "SimpleData"):
                key = simple_data.get("name")
                if key:
                    props[key] = simple_data.text.strip() if simple_data.text else ""

    return props


def _walk_kml_container(
    elem: etree._Element,
    folder_stack: list[str],
    features: list[ParsedFeature],
    warnings: list[str],
    settings: Settings,
) -> None:
    """Recursively walk Folders, Documents, and Placemarks."""
    tag = _local_name(elem)

    if tag == "Placemark":
        if len(features) >= settings.max_features:
            if len(warnings) < settings.max_warnings:
                limit = settings.max_features
                warnings.append(f"Reached feature limit of {limit}; further features omitted")
            return

        folder_path = "/".join(folder_stack)
        props = _extract_placemark_properties(elem, folder_path)

        # Look for geometry elements inside Placemark
        geom: BaseGeometry | None = None
        geom_type = "None"
        msg: str | None = None

        geometry_tags = {
            "Point",
            "LineString",
            "LinearRing",
            "Polygon",
            "MultiGeometry",
            "Track",
            "MultiTrack",
            "Model",
        }
        found_geom_elem = False

        for child in elem:
            c_tag = _local_name(child)
            if c_tag in geometry_tags or c_tag.startswith("gx:"):
                found_geom_elem = True
                geom, geom_type, msg = _parse_geometry_element(child)
                break

        if not found_geom_elem:
            msg = "Placemark has no geometry element"

        feature = ParsedFeature(
            index=len(features),
            geometry=geom,
            geometry_type=geom_type,
            properties=props,
            message=msg,
        )
        features.append(feature)
        return

    # Check if folder or document container
    is_folder = tag in {"Folder", "Document"}
    if is_folder:
        name_elem = _find_direct_child(elem, "name")
        folder_name = name_elem.text.strip() if name_elem is not None and name_elem.text else ""
        if folder_name:
            folder_stack.append(folder_name)

    for child in elem:
        if len(features) >= settings.max_features:
            break
        _walk_kml_container(child, folder_stack, features, warnings, settings)

    if is_folder and folder_stack and folder_name:
        folder_stack.pop()


def parse_kml_bytes(data: bytes, settings: Settings | None = None) -> ParsedFile:
    """Parse raw KML bytes safely."""
    settings = settings or get_settings()

    if not data or not data.strip():
        raise InvalidFileError("KML file is empty")

    # Guard against XXE and Billion Laughs DoS attacks by prohibiting DTD/entity declarations
    data_upper = data.upper()
    if b"<!DOCTYPE" in data_upper or b"<!ENTITY" in data_upper:
        raise UnsafeXMLError("XML DTD and entity declarations are forbidden in KML uploads")

    # Hardened XML parser
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
        huge_tree=False,
        remove_comments=True,
        recover=False,
    )

    try:
        root = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as exc:
        msg = str(exc)
        if "entity" in msg.lower() or "expansion" in msg.lower():
            raise UnsafeXMLError(f"XML entity expansion / XXE rejected: {exc}") from exc
        raise InvalidFileError(f"Malformed KML XML: {exc}") from exc

    features: list[ParsedFeature] = []
    warnings: list[str] = []

    _walk_kml_container(root, [], features, warnings, settings)

    if not features:
        warnings.append("KML file contains no Placemarks")

    return ParsedFile(
        file_type=FileType.KML,
        crs=WGS84,
        features=features,
        warnings=warnings,
    )


def parse_kmz_bytes(data: bytes, settings: Settings | None = None) -> ParsedFile:
    """Parse KMZ archive (zipped KML) safely."""
    settings = settings or get_settings()

    members = read_safe_zip(data, settings)

    # Find primary KML file in KMZ
    kml_candidates = [name for name in members if name.lower().endswith(".kml")]
    if not kml_candidates:
        raise InvalidFileError("KMZ archive does not contain any .kml file")

    # Prefer 'doc.kml' if present, otherwise first candidate
    primary_kml = next((c for c in kml_candidates if c.lower() == "doc.kml"), kml_candidates[0])
    kml_bytes = members[primary_kml]

    parsed = parse_kml_bytes(kml_bytes, settings)
    return ParsedFile(
        file_type=FileType.KMZ,
        crs=parsed.crs,
        features=parsed.features,
        warnings=parsed.warnings,
    )
