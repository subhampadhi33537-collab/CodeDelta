"""Projects repository – pure async SQL via psycopg."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from psycopg import AsyncConnection

from app.db.models import ProjectRow


async def create_project(
    conn: AsyncConnection, user_id: UUID, name: str, initial_prompt: str
) -> ProjectRow:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            insert into projects (user_id, name, initial_prompt)
            values (%s, %s, %s)
            returning id, user_id, name, initial_prompt, status, current_version, created_at, updated_at
            """,
            (user_id, name, initial_prompt),
        )
        row = await cur.fetchone()
        return ProjectRow.model_validate(dict(row))


async def get_project_by_id(
    conn: AsyncConnection, project_id: UUID, user_id: UUID
) -> Optional[ProjectRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select id, user_id, name, initial_prompt, status, current_version, created_at, updated_at
            from projects where id = %s and user_id = %s
            """,
            (project_id, user_id),
        )
        row = await cur.fetchone()
        return ProjectRow.model_validate(dict(row)) if row else None


async def list_projects_by_user(
    conn: AsyncConnection, user_id: UUID, limit: int = 50, offset: int = 0
) -> List[ProjectRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select id, user_id, name, initial_prompt, status, current_version, created_at, updated_at
            from projects where user_id = %s order by updated_at desc limit %s offset %s
            """,
            (user_id, limit, offset),
        )
        rows = await cur.fetchall()
        return [ProjectRow.model_validate(dict(r)) for r in rows]


async def update_project(
    conn: AsyncConnection,
    project_id: UUID,
    user_id: UUID,
    name: Optional[str] = None,
    status: Optional[str] = None,
    current_version: Optional[int] = None,
) -> Optional[ProjectRow]:
    fields, vals = ["updated_at = now()"], []
    if name is not None:
        fields.append("name = %s"); vals.append(name)
    if status is not None:
        fields.append("status = %s"); vals.append(status)
    if current_version is not None:
        fields.append("current_version = %s"); vals.append(current_version)
    vals.extend([project_id, user_id])
    async with conn.cursor() as cur:
        await cur.execute(
            f"update projects set {', '.join(fields)} where id = %s and user_id = %s "
            "returning id, user_id, name, initial_prompt, status, current_version, created_at, updated_at",
            vals,
        )
        row = await cur.fetchone()
        return ProjectRow.model_validate(dict(row)) if row else None


async def delete_project(
    conn: AsyncConnection, project_id: UUID, user_id: UUID
) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            "delete from projects where id = %s and user_id = %s",
            (project_id, user_id),
        )
        return cur.rowcount > 0
