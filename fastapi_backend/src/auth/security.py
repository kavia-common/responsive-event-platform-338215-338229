"""
Authentication/security helpers.

Environment variables required:
- JWT_SECRET: secret used to sign JWTs (HS256)
- JWT_EXPIRES_MINUTES: optional, defaults to 60

Tokens are standard "Bearer <token>" used with OAuth2PasswordBearer.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET env var is required for authentication.")
    return secret


def _get_exp_minutes() -> int:
    raw = os.getenv("JWT_EXPIRES_MINUTES", "60")
    try:
        return int(raw)
    except ValueError:
        return 60


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return PWD_CONTEXT.hash(password)


# PUBLIC_INTERFACE
def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return PWD_CONTEXT.verify(password, password_hash)


# PUBLIC_INTERFACE
def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """
    Create a signed JWT access token.

    subject: typically the user id string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=_get_exp_minutes())
    payload: dict[str, Any] = {"sub": subject, "iat": int(now.timestamp()), "exp": int(expire.timestamp())}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)


# PUBLIC_INTERFACE
def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token, raising JWTError if invalid."""
    return jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])
