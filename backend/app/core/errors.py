"""Domain exceptions.

Each exception carries a stable machine-readable ``code`` and the HTTP status it maps
to, so the API layer can render a consistent error envelope without ``if`` ladders.
"""

from __future__ import annotations

from typing import Any


class GeoMetricsError(Exception):
    status_code: int = 400
    code: str = "BAD_REQUEST"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedFormatError(GeoMetricsError):
    status_code = 415
    code = "UNSUPPORTED_FORMAT"


class UploadTooLargeError(GeoMetricsError):
    status_code = 413
    code = "UPLOAD_TOO_LARGE"


class InvalidFileError(GeoMetricsError):
    """The file was accepted but its contents cannot be processed."""

    status_code = 422
    code = "INVALID_FILE"


class UnsafeArchiveError(InvalidFileError):
    code = "UNSAFE_ARCHIVE"


class UnsafeXMLError(InvalidFileError):
    code = "UNSAFE_XML"


class CRSError(InvalidFileError):
    code = "CRS_UNRESOLVED"


class NotFoundError(GeoMetricsError):
    status_code = 404
    code = "NOT_FOUND"


class FileNotReadyError(GeoMetricsError):
    status_code = 409
    code = "FILE_NOT_READY"
