from __future__ import annotations

import io
import zipfile

import pytest

from app.core.config import Settings
from app.core.errors import (
    InvalidFileError,
    UnsafeArchiveError,
    UnsafeXMLError,
    UnsupportedFormatError,
)
from app.parsers.base import parse_geospatial_file
from app.parsers.kml import parse_kml_bytes
from app.parsers.safe_zip import read_safe_zip


def test_reject_unsupported_extensions() -> None:
    for bad_name in ["survey.exe", "survey.csv", "survey.geojson", "survey.tar.gz"]:
        with pytest.raises(UnsupportedFormatError):
            parse_geospatial_file(b"data", bad_name)


def test_reject_kml_with_zip_payload() -> None:
    # Rename attack: someone uploaded a zip file disguised as .kml
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("test.txt", b"content")
    with pytest.raises(InvalidFileError, match=r"did you mean \.kmz"):
        parse_geospatial_file(buf.getvalue(), "disguised.kml")


def test_reject_kmz_with_plain_xml_payload() -> None:
    with pytest.raises(InvalidFileError, match="not a valid ZIP archive"):
        parse_geospatial_file(b"<kml>not a zip</kml>", "disguised.kmz")


def test_billion_laughs_dos_is_rejected() -> None:
    # Classic Billion Laughs exponential entity expansion attack
    payload = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [
     <!ENTITY lol "lol">
     <!ELEMENT lolz (#PCDATA)>
     <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
     <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
     <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
    ]>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Placemark>
        <name>&lol3;</name>
        <Point><coordinates>0,0</coordinates></Point>
      </Placemark>
    </kml>
    """
    with pytest.raises((UnsafeXMLError, InvalidFileError)):
        parse_kml_bytes(payload)


def test_xxe_external_file_access_is_rejected() -> None:
    # XXE external entity retrieval attempt
    payload = b"""<?xml version="1.0"?>
    <!DOCTYPE r [
      <!ENTITY file SYSTEM "file:///etc/passwd">
    ]>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Placemark>
        <name>&file;</name>
        <Point><coordinates>0,0</coordinates></Point>
      </Placemark>
    </kml>
    """
    with pytest.raises((UnsafeXMLError, InvalidFileError)):
        parse_kml_bytes(payload)


def test_zip_decompression_bomb_is_aborted() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # High compression ratio repeating zeroes
        zf.writestr("bomb.bin", b"\x00" * (20 * 1024 * 1024))

    settings = Settings(max_uncompressed_bytes=2 * 1024 * 1024)
    with pytest.raises(UnsafeArchiveError, match="uncompressed size exceeds limit"):
        read_safe_zip(buf.getvalue(), settings=settings)
