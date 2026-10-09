"""Safe in-memory ZIP archive reader with guards against common archive attacks.

Protections:
- Zip-Slip path traversal (absolute paths, '..' components).
- Zip bombs / decompression bombs (uncompressed byte ceiling).
- Member count flooding (maximum member limit).
- Password-protected / encrypted archives.
- Archive extraction is strictly in-memory (no disk writes, avoiding lock / leak issues).
"""

from __future__ import annotations

import io
import zipfile

from app.core.config import Settings, get_settings
from app.core.errors import InvalidFileError, UnsafeArchiveError

ZIP_LOCAL_FILE_MAGIC = b"PK\x03\x04"
ZIP_EMPTY_MAGIC = b"PK\x05\x06"


def is_zip_bytes(data: bytes) -> bool:
    """Quick check for standard ZIP file header signatures."""
    return data.startswith(ZIP_LOCAL_FILE_MAGIC) or data.startswith(ZIP_EMPTY_MAGIC)


def sanitize_zip_path(raw_name: str) -> str:
    """Validate and normalize an archive member path, blocking path traversal."""
    # Normalize slashes
    clean_path = raw_name.replace("\\", "/").strip()

    # Reject absolute paths (Unix or Windows drive letter)
    if clean_path.startswith("/") or (len(clean_path) >= 2 and clean_path[1] == ":"):
        raise UnsafeArchiveError(f"ZIP member contains absolute path: {raw_name}")

    parts = [part for part in clean_path.split("/") if part and part != "."]
    if ".." in parts:
        raise UnsafeArchiveError(
            f"ZIP member contains directory traversal component '..': {raw_name}"
        )

    return "/".join(parts)


def read_safe_zip(
    data: bytes,
    settings: Settings | None = None,
) -> dict[str, bytes]:
    """Inspect and unpack a ZIP archive safely into memory.

    Returns a mapping of normalized relative filename to member file bytes.
    Directory members are excluded from the returned dictionary.
    """
    settings = settings or get_settings()

    if not is_zip_bytes(data):
        raise InvalidFileError("Uploaded file is not a valid ZIP archive (invalid header)")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise InvalidFileError(f"Corrupted or invalid ZIP archive: {exc}") from exc

    infolist = zf.infolist()
    if len(infolist) > settings.max_zip_members:
        limit = settings.max_zip_members
        count = len(infolist)
        raise UnsafeArchiveError(f"ZIP archive contains {count} members, exceeding limit {limit}")

    total_uncompressed = 0
    members: dict[str, bytes] = {}

    for info in infolist:
        # Check for encrypted members
        if info.flag_bits & 0x1:
            raise InvalidFileError(
                f"Encrypted or password-protected ZIP members are not supported: {info.filename}"
            )

        clean_name = sanitize_zip_path(info.filename)
        if not clean_name or info.is_dir() or clean_name.endswith("/"):
            continue

        # Check declared uncompressed size against bomb limit
        total_uncompressed += info.file_size
        if total_uncompressed > settings.max_uncompressed_bytes:
            ceiling = settings.max_uncompressed_bytes
            raise UnsafeArchiveError(
                f"ZIP archive uncompressed size exceeds limit of {ceiling} bytes"
            )

        # Read content and verify actual uncompressed size
        try:
            member_bytes = zf.read(info)
        except Exception as exc:
            raise InvalidFileError(f"Failed to read ZIP member '{info.filename}': {exc}") from exc

        if len(member_bytes) != info.file_size:
            raise InvalidFileError(f"Corrupted ZIP member size mismatch for '{info.filename}'")

        members[clean_name] = member_bytes

    if not members:
        raise InvalidFileError("ZIP archive is empty or contains no files")

    return members
