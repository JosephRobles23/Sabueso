from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

import asyncpg

from src.settings import Settings


@runtime_checkable
class PoolLike(Protocol):
    """Subset of asyncpg.Pool used by the API.

    Defined as a protocol so tests can pass a fake without subclassing asyncpg internals.
    """

    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchrow(self, query: str, *args: Any) -> Any | None: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> str: ...
    async def close(self) -> None: ...


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Make JSON/JSONB round-trip cleanly with Python dict/list instead of raw str.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def create_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=settings.supabase_db_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        command_timeout=settings.db_pool_command_timeout,
        init=_init_connection,
    )


async def healthcheck(pool: PoolLike) -> bool:
    result = await pool.fetchval("SELECT 1")
    return bool(result == 1)
