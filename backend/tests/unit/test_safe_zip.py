from __future__ import annotations

import io
import zipfile

import pytest

from app.core.config import Settings
from app.core.errors import InvalidFileError, UnsafeArchiveError
from app.parsers.safe_zip import is_zip_bytes, read_safe_zip, sanitize_zip_path


def create_zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_is_zip_bytes() -> None:
    assert is_zip_bytes(b"PK\x03\x04\x14\x00...")
    assert not is_zip_bytes(b"<?xml version='1.0'?>")
    assert not is_zip_bytes(b"")


def test_read_valid_zip() -> None:
    data = create_zip_bytes({"folder/file1.txt": b"hello", "file2.txt": b"world"})
    result = read_safe_zip(data)
    assert result == {"folder/file1.txt": b"hello", "file2.txt": b"world"}


@pytest.mark.parametrize(
    "traversal_path",
    [
        "../etc/passwd",
        "foo/../../etc/passwd",
        "/etc/passwd",
        "C:\\Windows\\system.ini",
        "foo/..\\bar",
    ],
)
def test_zip_slip_path_traversal_is_blocked(traversal_path: str) -> None:
    with pytest.raises(UnsafeArchiveError, match=r"traversal|absolute"):
        sanitize_zip_path(traversal_path)


def test_zip_with_traversal_member_raises() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", b"malicious")
    with pytest.raises(UnsafeArchiveError, match="directory traversal"):
        read_safe_zip(buf.getvalue())


def test_zip_max_members_limit() -> None:
    members = {f"file_{i}.txt": b"x" for i in range(10)}
    data = create_zip_bytes(members)

    settings = Settings(max_zip_members=5)
    with pytest.raises(UnsafeArchiveError, match=r"exceeding limit 5"):
        read_safe_zip(data, settings=settings)


def test_zip_bomb_uncompressed_ceiling() -> None:
    # 5 MB uncompressed in zip
    large_payload = b"0" * (5 * 1024 * 1024)
    data = create_zip_bytes({"large.txt": large_payload})

    settings = Settings(max_uncompressed_bytes=1024 * 1024)  # 1 MB limit
    with pytest.raises(UnsafeArchiveError, match="uncompressed size exceeds limit"):
        read_safe_zip(data, settings=settings)


def test_corrupted_or_non_zip_raises() -> None:
    with pytest.raises(InvalidFileError, match="not a valid ZIP archive"):
        read_safe_zip(b"not a zip file at all")


def test_empty_zip_raises() -> None:
    empty_zip = create_zip_bytes({})
    with pytest.raises(InvalidFileError, match="empty or contains no files"):
        read_safe_zip(empty_zip)
