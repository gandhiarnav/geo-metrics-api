"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import router as files_router
from app.core.config import Settings, get_settings
from app.core.errors import GeoMetricsError
from app.core.logging import configure_logging
from app.db.session import init_db

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # Automatically ensure schema tables exist for local SQLite usage
    if settings.is_sqlite:
        init_db()

    app = FastAPI(
        title="Geo Metrics API",
        version=__version__,
        description=(
            "Upload a KML file or a zipped Shapefile, extract its features and get "
            "per-feature area (m²) and length (m) computed in an appropriate projected CRS."
        ),
    )
    app.state.settings = settings
    app.include_router(files_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(GeoMetricsError)
    async def _domain_error_handler(_: Request, exc: GeoMetricsError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.get("/health", tags=["meta"], summary="Liveness probe")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
