"""
backend/app/services/jwt.py
───────────────────────────
PyJWT-based authentication token service with HS256.
Claims are validated by TokenPayload (sub, email, iat, exp).
"""

from __future__ import annotations

import time
from typing import Tuple
from uuid import UUID

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.config import get_settings
from app.schemas.auth import TokenPayload

ALGORITHM = "HS256"


def create_access_token(
    user_id: UUID,
    email: str,
    expires_minutes: int | None = None,
) -> Tuple[str, int]:
    """
    Create a signed JWT access token.
    Returns (token_str, expires_in_seconds).
    """
    settings = get_settings()
    secret = settings.JWT_SECRET
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured in settings.")

    minutes = expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_MINUTES
    expires_in_seconds = minutes * 60
    now = int(time.time())
    exp = now + expires_in_seconds

    payload = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "iat": now,
        "exp": exp,
    }

    token = jwt.encode(payload, secret, algorithm=ALGORITHM)
    return token, expires_in_seconds


def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT access token.
    Validates signature, expiration, and ensures claims match TokenPayload schema.
    Raises ExpiredSignatureError or InvalidTokenError on failure.
    """
    settings = get_settings()
    secret = settings.JWT_SECRET
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured in settings.")

    raw_payload = jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "email", "iat", "exp"]},
    )
    # Validates claims against TokenPayload (UUID, EmailStr, timestamps)
    return TokenPayload.model_validate(raw_payload)
