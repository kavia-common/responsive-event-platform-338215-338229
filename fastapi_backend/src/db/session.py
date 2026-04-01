"""
Database session/engine setup for the FastAPI backend.

Uses environment variables provided by the database container:
- POSTGRES_URL
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_DB
- POSTGRES_PORT
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_ENGINE = None
_SessionLocal = None


def _build_postgres_url() -> str:
    """
    Build SQLAlchemy database URL from environment variables.

    We intentionally do not assume POSTGRES_URL format; if POSTGRES_URL is set,
    we use it directly as the SQLAlchemy URL. Otherwise we assemble a standard
    postgres URL from component env vars.
    """
    direct = os.getenv("POSTGRES_URL")
    if direct:
        return direct

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_DB")
    port = os.getenv("POSTGRES_PORT", "5432")
    host = os.getenv("POSTGRES_HOST", "localhost")  # optional; may not be present

    if not all([user, password, db]):
        missing = [k for k in ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"] if not os.getenv(k)]
        raise RuntimeError(
            "Database env vars missing: "
            + ", ".join(missing)
            + ". Provide POSTGRES_URL or the component vars."
        )

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_engine():
    """Return a singleton SQLAlchemy engine."""
    global _ENGINE, _SessionLocal
    if _ENGINE is None:
        db_url = _build_postgres_url()
        _ENGINE = create_engine(db_url, pool_pre_ping=True, future=True)
        _SessionLocal = sessionmaker(bind=_ENGINE, autocommit=False, autoflush=False, future=True)
    return _ENGINE


def get_sessionmaker():
    """Return a singleton sessionmaker."""
    get_engine()
    return _SessionLocal


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager yielding a Session and committing/rolling back appropriately."""
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy Session."""
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
