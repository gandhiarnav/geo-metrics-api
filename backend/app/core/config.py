"""Runtime configuration loaded from environment variables.

All application settings use the ``GEO_`` prefix, except ``DATABASE_URL`` which is
read verbatim so that platforms like Render can inject it directly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MB = 1024 * 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEO_", env_file=".env", extra="ignore")

    app_name: str = "geo-metrics-api"
    environment: str = "development"

    database_url: str = Field(
        default="sqlite:///./data/geometrics.db",
        validation_alias="DATABASE_URL",
    )

    # Upload & archive limits (defensive defaults sized for a 512 MB container).
    max_upload_bytes: int = 20 * MB
    max_uncompressed_bytes: int = 200 * MB
    max_zip_members: int = 50
    max_features: int = 50_000
    max_warnings: int = 50
    upload_chunk_bytes: int = 1 * MB

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        """Render/Heroku expose ``postgres://`` URLs; SQLAlchemy needs an explicit driver."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
