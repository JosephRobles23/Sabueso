"""Pool asyncpg compartido y helpers de transacción para los flows.

Supabase Postgres con pgvector. Conexión por SUPABASE_DB_URL.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

_pool: asyncpg.Pool | None = None


def _dsn() -> str:
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        raise RuntimeError("SUPABASE_DB_URL no está definida")
    return dsn


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            _dsn(),
            min_size=1,
            max_size=int(os.environ.get("PIPELINE_PG_MAX_CONNS", "10")),
            command_timeout=60,
            statement_cache_size=0,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def conn() -> AsyncIterator[asyncpg.Connection]:
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection


async def checkpoint_done(flow_id: str, external_id: str) -> bool:
    async with conn() as c:
        row = await c.fetchrow(
            "SELECT status FROM pipeline_checkpoints WHERE flow_id=$1 AND external_id=$2",
            flow_id,
            external_id,
        )
    return row is not None and row["status"] == "ok"


async def checkpoint_save(
    flow_id: str,
    external_id: str,
    status: str,
    *,
    error: str | None = None,
    metadata: dict | None = None,
) -> None:
    import json

    async with conn() as c:
        await c.execute(
            """
            INSERT INTO pipeline_checkpoints (flow_id, external_id, status, error, metadata)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT (flow_id, external_id) DO UPDATE
            SET status=EXCLUDED.status,
                error=EXCLUDED.error,
                metadata=EXCLUDED.metadata,
                processed_at=now()
            """,
            flow_id,
            external_id,
            status,
            error,
            json.dumps(metadata or {}),
        )
