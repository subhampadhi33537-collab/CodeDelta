"""
backend/app/db/pool.py
──────────────────────
Async psycopg 3 connection pool configured for Supabase PgBouncer pooler.
- Uses prepare_threshold=0 (required by PgBouncer transaction mode on port 6543)
- row_factory=dict_row returns results as standard Python dicts
- FastAPI dependency yields an async connection with automatic commit/rollback
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional
from urllib.parse import quote_plus

from fastapi import Depends
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Global singleton connection pool
_db_pool: Optional[AsyncConnectionPool] = None


def build_database_url(settings: Settings) -> str:
    """Resolve database URL from DATABASE_URL or component variables."""
    if settings.DATABASE_URL.strip():
        return settings.DATABASE_URL.strip()
    return (
        f"postgresql://{settings.DATABASE_USER}:{quote_plus(settings.DATABASE_PASSWORD)}"
        f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    )


async def init_db_pool(settings: Optional[Settings] = None) -> AsyncConnectionPool:
    """Initialize the global async database pool."""
    global _db_pool
    if _db_pool is not None:
        return _db_pool

    cfg = settings or get_settings()
    conninfo = build_database_url(cfg)

    logger.info("Initializing async psycopg connection pool...")
    _db_pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=10,
        timeout=30.0,
        max_idle=300.0,
        open=False,
        kwargs={
            "prepare_threshold": 0,  # Required for Supabase PgBouncer pooler (port 6543)
            "row_factory": dict_row,
            "autocommit": False,
        },
    )
    await _db_pool.open()
    logger.info("Async psycopg connection pool opened successfully.")
    return _db_pool


async def close_db_pool() -> None:
    """Close the global database pool on application shutdown."""
    global _db_pool
    if _db_pool is not None:
        logger.info("Closing async psycopg connection pool...")
        await _db_pool.close()
        _db_pool = None
        logger.info("Async psycopg connection pool closed.")


def get_db_pool() -> AsyncConnectionPool:
    """Get the active database pool instance."""
    if _db_pool is None:
        raise RuntimeError(
            "Database pool is not initialized. Ensure app lifespan has started."
        )
    return _db_pool


async def get_db_connection() -> AsyncGenerator:
    """
    FastAPI dependency yielding a psycopg async connection.
    Commits on successful completion of the route, rolls back on error.
    """
    pool = get_db_pool()
    async with pool.connection() as conn:
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
