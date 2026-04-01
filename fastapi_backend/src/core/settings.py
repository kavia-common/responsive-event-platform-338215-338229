"""
Centralized runtime settings for the FastAPI backend.

We keep environment parsing in one place to avoid scattered `os.getenv()` usage.

Contract:
- Inputs:
  - Environment variables (optional unless noted):
    - APP_ENV: "development"|"preview"|"production" (default: "development")
    - CORS_ALLOW_ORIGINS: comma-separated list of allowed origins (default: "*")
      Example:
        "https://vscode-internal-...:3000,http://localhost:3000"
    - POSTGRES_URL: optional full SQLAlchemy URL (preferred if provided)
    - POSTGRES_HOST: optional hostname (default: "localhost")
    - POSTGRES_PORT: optional port (default: "5000" to match postgresql_database container)
    - POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB: required if POSTGRES_URL is not set
    - JWT_SECRET: required for auth token signing/verification
    - JWT_EXPIRES_MINUTES: optional (default: "60")
- Outputs:
  - Settings object with normalized values used by the app.
- Errors:
  - Raises RuntimeError for missing critical configuration (e.g., JWT_SECRET, DB vars).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


def _parse_csv(value: str) -> List[str]:
    """Parse a comma-separated string into a list of trimmed, non-empty items."""
    items = [v.strip() for v in value.split(",")]
    return [v for v in items if v]


@dataclass(frozen=True)
class Settings:
    """Typed settings container used across the backend."""

    app_env: str
    cors_allow_origins: List[str]

    postgres_url: str | None
    postgres_host: str
    postgres_port: str
    postgres_user: str | None
    postgres_password: str | None
    postgres_db: str | None


_SETTINGS: Settings | None = None


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """
    Return a singleton Settings instance.

    This is the single entrypoint for reading/normalizing environment configuration.
    """
    global _SETTINGS
    if _SETTINGS is not None:
        return _SETTINGS

    app_env = (os.getenv("APP_ENV") or "development").strip().lower()

    cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    cors_allow_origins = ["*"] if cors_raw == "*" else _parse_csv(cors_raw)

    _SETTINGS = Settings(
        app_env=app_env,
        cors_allow_origins=cors_allow_origins,
        postgres_url=os.getenv("POSTGRES_URL"),
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        # IMPORTANT: default port matches postgresql_database container startup.sh (5000),
        # not local system default 5432.
        postgres_port=os.getenv("POSTGRES_PORT", "5000"),
        postgres_user=os.getenv("POSTGRES_USER"),
        postgres_password=os.getenv("POSTGRES_PASSWORD"),
        postgres_db=os.getenv("POSTGRES_DB"),
    )
    return _SETTINGS
