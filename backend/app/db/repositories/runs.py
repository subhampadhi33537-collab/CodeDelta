"""Agent runs repository – pure async SQL via psycopg."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from psycopg import AsyncConnection

from app.db.models import AgentRunRow


async def create_run(
    conn: AsyncConnection,
    project_id: UUID,
    user_id: UUID,
    intent: Optional[str] = None,
    model_choice: Optional[str] = None,
) -> AgentRunRow:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            insert into agent_runs (project_id, user_id, intent, model_choice)
            values (%s, %s, %s, %s)
            returning id, project_id, user_id, intent, status, model_choice, error, started_at, ended_at, created_at
            """,
            (project_id, user_id, intent, model_choice),
        )
        row = await cur.fetchone()
        return AgentRunRow.model_validate(dict(row))


async def get_run_by_id(
    conn: AsyncConnection, run_id: UUID, user_id: UUID
) -> Optional[AgentRunRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select id, project_id, user_id, intent, status, model_choice, error, started_at, ended_at, created_at
            from agent_runs where id = %s and user_id = %s
            """,
            (run_id, user_id),
        )
        row = await cur.fetchone()
        return AgentRunRow.model_validate(dict(row)) if row else None


async def update_run_status(
    conn: AsyncConnection,
    run_id: UUID,
    status: str,
    error: Optional[str] = None,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
) -> Optional[AgentRunRow]:
    fields, vals = ["status = %s"], [status]
    if error is not None:
        fields.append("error = %s"); vals.append(error)
    if started_at is not None:
        fields.append("started_at = %s"); vals.append(started_at)
    if ended_at is not None:
        fields.append("ended_at = %s"); vals.append(ended_at)
    vals.append(run_id)
    async with conn.cursor() as cur:
        await cur.execute(
            f"update agent_runs set {', '.join(fields)} where id = %s "
            "returning id, project_id, user_id, intent, status, model_choice, error, started_at, ended_at, created_at",
            vals,
        )
        row = await cur.fetchone()
        return AgentRunRow.model_validate(dict(row)) if row else None


async def list_runs_by_project(
    conn: AsyncConnection, project_id: UUID, user_id: UUID
) -> List[AgentRunRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select id, project_id, user_id, intent, status, model_choice, error, started_at, ended_at, created_at
            from agent_runs where project_id = %s and user_id = %s order by created_at desc
            """,
            (project_id, user_id),
        )
        rows = await cur.fetchall()
        return [AgentRunRow.model_validate(dict(r)) for r in rows]
