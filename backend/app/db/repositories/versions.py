"""Project versions repository – pure async SQL via psycopg."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from psycopg import AsyncConnection

from app.db.models import ProjectVersionRow


async def create_version(
    conn: AsyncConnection,
    project_id: UUID,
    user_id: UUID,
    version: int,
    drive_file_id: str,
    size_bytes: Optional[int] = None,
    sha256: Optional[str] = None,
    run_id: Optional[UUID] = None,
) -> ProjectVersionRow:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            insert into project_versions (project_id, user_id, version, drive_file_id, size_bytes, sha256, run_id)
            values (%s, %s, %s, %s, %s, %s, %s)
            returning id, project_id, user_id, version, drive_file_id, size_bytes, sha256, run_id, created_at
            """,
            (project_id, user_id, version, drive_file_id, size_bytes, sha256, run_id),
        )
        row = await cur.fetchone()
        return ProjectVersionRow.model_validate(dict(row))


async def get_version(
    conn: AsyncConnection, project_id: UUID, user_id: UUID, version: int
) -> Optional[ProjectVersionRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select id, project_id, user_id, version, drive_file_id, size_bytes, sha256, run_id, created_at
            from project_versions where project_id = %s and user_id = %s and version = %s
            """,
            (project_id, user_id, version),
        )
        row = await cur.fetchone()
        return ProjectVersionRow.model_validate(dict(row)) if row else None


async def list_versions_by_project(
    conn: AsyncConnection, project_id: UUID, user_id: UUID
) -> List[ProjectVersionRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select id, project_id, user_id, version, drive_file_id, size_bytes, sha256, run_id, created_at
            from project_versions where project_id = %s and user_id = %s order by version desc
            """,
            (project_id, user_id),
        )
        rows = await cur.fetchall()
        return [ProjectVersionRow.model_validate(dict(r)) for r in rows]


async def delete_older_versions(
    conn: AsyncConnection, project_id: UUID, user_id: UUID, keep_count: int = 20
) -> List[str]:
    """Delete versions beyond the newest keep_count; returns deleted drive_file_ids."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            delete from project_versions
            where project_id = %s and user_id = %s and id not in (
                select id from project_versions
                where project_id = %s and user_id = %s
                order by version desc limit %s
            )
            returning drive_file_id
            """,
            (project_id, user_id, project_id, user_id, keep_count),
        )
        rows = await cur.fetchall()
        return [r["drive_file_id"] for r in rows]
