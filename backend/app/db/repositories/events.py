"""Agent events repository – pure async SQL via psycopg."""

from __future__ import annotations

import json
from typing import Any, List, Optional
from uuid import UUID

from psycopg import AsyncConnection

from app.db.models import AgentEventRow


async def append_event(
    conn: AsyncConnection,
    run_id: UUID,
    seq: int,
    event_type: str,
    agent: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> AgentEventRow:
    payload_json = json.dumps(payload) if payload is not None else None
    async with conn.cursor() as cur:
        await cur.execute(
            """
            insert into agent_events (run_id, seq, agent, type, payload)
            values (%s, %s, %s, %s, %s::jsonb)
            returning id, run_id, seq, agent, type, payload, created_at
            """,
            (run_id, seq, agent, event_type, payload_json),
        )
        row = await cur.fetchone()
        return AgentEventRow.model_validate(dict(row))


async def list_events_by_run(
    conn: AsyncConnection, run_id: UUID, after_seq: int = 0
) -> List[AgentEventRow]:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            select id, run_id, seq, agent, type, payload, created_at
            from agent_events where run_id = %s and seq > %s
            order by seq asc
            """,
            (run_id, after_seq),
        )
        rows = await cur.fetchall()
        return [AgentEventRow.model_validate(dict(r)) for r in rows]
