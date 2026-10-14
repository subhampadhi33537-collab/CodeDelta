"""
backend/app/schemas/auth.py
───────────────────────────
Pydantic v2 authentication schemas and strict validators per spec Section 7.
"""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be blank or contain only whitespace.")
        if len(stripped) < 2:
            raise ValueError("Name must be at least 2 characters long.")
        return stripped

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserPublic(BaseModel):
    """The only user shape ever returned in API responses. Never includes password_hash."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # in seconds
    user: UserPublic


class TokenPayload(BaseModel):
    """Validates decoded JWT claims."""
    sub: UUID
    email: EmailStr
    iat: int
    exp: int
