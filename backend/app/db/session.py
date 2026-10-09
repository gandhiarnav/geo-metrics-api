"""Database engine and session management supporting SQLite and PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base


def _ensure_sqlite_dir(url: str) -> None:
    """Ensure directory exists when using a SQLite file database."""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        db_path = url.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)


@lru_cache(maxsize=1)
def get_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    url = database_url or settings.database_url

    _ensure_sqlite_dir(url)

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


@lru_cache(maxsize=1)
def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    engine = get_engine(database_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a transactional database session."""
    session_factory = get_session_factory()
    with session_factory() as session:
        yield session


def init_db(engine: Engine | None = None) -> None:
    """Create all tables in the database (used in test suite and standalone startup)."""
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)
