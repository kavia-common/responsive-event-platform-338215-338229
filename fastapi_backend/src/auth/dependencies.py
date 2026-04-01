"""FastAPI dependencies for authentication/authorization."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.security import decode_token
from src.db.models import User, UserRole
from src.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


# PUBLIC_INTERFACE
def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    """Resolve the authenticated user from Bearer JWT."""
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if not sub:
            raise _unauthorized("Invalid token: missing subject")
        user_id = int(sub)
    except (JWTError, ValueError):
        raise _unauthorized("Invalid token")

    user = db.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise _unauthorized("User not found or inactive")
    return user


# PUBLIC_INTERFACE
def require_role(*roles: UserRole):
    """Factory for a dependency that requires the current user to have one of the given roles."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _dep
