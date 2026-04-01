"""
Database session/engine setup for the FastAPI backend.

Uses environment variables provided by the database container:
- POSTGRES_URL (optional, full SQLAlchemy URL)
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_DB
- POSTGRES_PORT
- POSTGRES_HOST (optional; defaults to "localhost")

Integration note:
- The bundled `postgresql_database` container listens on port 5000 by default, so this
  backend defaults POSTGRES_PORT to 5000 (via Settings) unless overridden.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.settings import get_settings

_ENGINE = None
_SessionLocal = None


def _build_postgres_url() -> str:
    """
    Build SQLAlchemy database URL from environment variables.

    Contract:
    - If POSTGRES_URL is set, it is used as-is (must be a valid SQLAlchemy URL).
      Examples:
        postgresql+psycopg2://user:pass@host:5000/myapp
        postgresql://user:pass@host:5000/myapp
    - Otherwise, POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB must be set and the URL
      is assembled from components.
    """
    s = get_settings()

    if s.postgres_url:
        return s.postgres_url

    if not all([s.postgres_user, s.postgres_password, s.postgres_db]):
        missing = [
            k
            for k, v in [
                ("POSTGRES_USER", s.postgres_user),
                ("POSTGRES_PASSWORD", s.postgres_password),
                ("POSTGRES_DB", s.postgres_db),
            ]
            if not v
        ]
        raise RuntimeError(
            "Database env vars missing: "
            + ", ".join(missing)
            + ". Provide POSTGRES_URL or the component vars."
        )

    return (
        "postgresql+psycopg2://"
        f"{s.postgres_user}:{s.postgres_password}"
        f"@{s.postgres_host}:{s.postgres_port}/{s.postgres_db}"
    )


def get_engine():
    """Return a singleton SQLAlchemy engine."""
    global _ENGINE, _SessionLocal
    if _ENGINE is None:
        db_url = _build_postgres_url()
        _ENGINE = create_engine(db_url, pool_pre_ping=True, future=True)
        _SessionLocal = sessionmaker(
            bind=_ENGINE, autocommit=False, autoflush=False, future=True
        )
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
