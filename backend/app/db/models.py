"""
backend/app/db/models.py
────────────────────────
Pydantic v2 row models representing database records from Supabase Postgres.
Matches the exact schema defined in backend/db/migrations/001_init.sql.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    password_hash: str
    drive_folder_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime


class ProjectRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    initial_prompt: str
    status: str = "draft"  # draft | building | ready | failed
    current_version: int = 0
    created_at: datetime
    updated_at: datetime


class ProjectVersionRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    user_id: UUID
    version: int
    drive_file_id: str
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    run_id: Optional[UUID] = None
    created_at: datetime


class MessageRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    role: str  # user | assistant
    content: str
    created_at: datetime


class AgentRunRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    user_id: UUID
    intent: Optional[str] = None
    status: str = "queued"  # queued | running | done | failed | cancelled
    model_choice: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime


class AgentEventRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: UUID
    seq: int
    agent: Optional[str] = None
    type: str
    payload: Optional[dict[str, Any]] = None
    created_at: datetime


class ModelUsageRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: Optional[UUID] = None
    agent: Optional[str] = None
    provider: Optional[str] = None
    model_id: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    latency_ms: Optional[int] = None
    success: Optional[bool] = None
    created_at: datetime
