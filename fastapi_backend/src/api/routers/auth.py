from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import TokenResponse, UserCreate, UserLogin, UserPublic
from src.auth.security import create_access_token, hash_password, verify_password
from src.db.models import User, UserRole
from src.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a user with email/password and returns the public user profile.",
    operation_id="auth_register",
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> UserPublic:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=UserRole.user,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        created_at=user.created_at,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Validates credentials and returns a JWT access token.",
    operation_id="auth_login",
)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role.value})
    return TokenResponse(access_token=token, token_type="bearer")
