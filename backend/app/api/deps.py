"""FastAPI request dependencies."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.repository import FileRepository
from app.db.session import get_db


def get_db_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_repository(session: Session = Depends(get_db_session)) -> FileRepository:
    return FileRepository(session)
