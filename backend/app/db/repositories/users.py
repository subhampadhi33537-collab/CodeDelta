"""Users repository – pure async SQL via psycopg."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from psycopg import AsyncConnection

from app.db.models import UserRow


async def create_user(
    conn: AsyncConnection, name: str, email: str, password_hash: str
) -> UserRow:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            insert into users (name, email, password_hash)
            values (%s, %s, %s)
            returning id, name, email, password_hash, drive_folder_id, is_active, created_at
            """,
            (name, email, password_hash),
        )
        row = await cur.fetchone()
        return UserRow.model_validate(dict(row))


async def get_user_by_id(
    conn: AsyncConnection, user_id: UUID
) -> Optional[UserRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select id, name, email, password_hash, drive_folder_id, is_active, created_at
            from users where id = %s
            """,
            (user_id,),
        )
        row = await cur.fetchone()
        return UserRow.model_validate(dict(row)) if row else None


async def get_user_by_email(
    conn: AsyncConnection, email: str
) -> Optional[UserRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select id, name, email, password_hash, drive_folder_id, is_active, created_at
            from users where email = %s
            """,
            (email.strip().lower(),),
        )
        row = await cur.fetchone()
        return UserRow.model_validate(dict(row)) if row else None


async def update_user_drive_folder(
    conn: AsyncConnection, user_id: UUID, folder_id: str
) -> Optional[UserRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            update users set drive_folder_id = %s
            where id = %s
            returning id, name, email, password_hash, drive_folder_id, is_active, created_at
            """,
            (folder_id, user_id),
        )
        row = await cur.fetchone()
        return UserRow.model_validate(dict(row)) if row else None
