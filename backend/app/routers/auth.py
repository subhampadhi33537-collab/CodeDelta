"""
backend/app/routers/auth.py
───────────────────────────
Authentication endpoints: register, login, me.
Strict Pydantic v2 validation and response models throughout.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection

from app.db.models import UserRow
from app.db.pool import get_db_connection
from app.db.repositories.users import create_user, get_user_by_email
from app.dependencies import get_current_user
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.services.jwt import create_access_token
from app.services.password import hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    req: RegisterRequest,
    conn: AsyncConnection = Depends(get_db_connection),
) -> TokenResponse:
    """
    Register a new user:
    - Rejects duplicate email with 409
    - Hashes password using Argon2id
    - Inserts user and returns access token
    """
    existing = await get_user_by_email(conn, req.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    pwd_hash = hash_password(req.password)
    user = await create_user(
        conn,
        name=req.name,
        email=req.email,
        password_hash=pwd_hash,
    )
    logger.info("Registered new user with id=%s", user.id)

    access_token, expires_in = create_access_token(user.id, str(user.email))
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserPublic.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and get access token",
)
async def login(
    req: LoginRequest,
    conn: AsyncConnection = Depends(get_db_connection),
) -> TokenResponse:
    """
    Authenticate user:
    - Returns generic 401 on any failure (email not found, wrong password, inactive)
    - Returns access token and public user profile
    """
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = await get_user_by_email(conn, req.email)
    if user is None:
        raise generic_error

    if not verify_password(req.password, user.password_hash):
        raise generic_error

    if not user.is_active:
        raise generic_error

    access_token, expires_in = create_access_token(user.id, str(user.email))
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserPublic.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def get_me(
    current_user: UserRow = Depends(get_current_user),
) -> UserPublic:
    """Return the currently authenticated user's public profile."""
    return UserPublic.model_validate(current_user)
