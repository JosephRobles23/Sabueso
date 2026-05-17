"""Cache layer respaldado por la tabla ``tool_cache`` de Supabase.

Schema (creada en migration 003_operational_tables.sql)::

    CREATE TABLE tool_cache (
        key         TEXT PRIMARY KEY,
        value       JSONB NOT NULL,
        expires_at  TIMESTAMPTZ NOT NULL
    );

Cleanup horario lo hace pg_cron (005_triggers.sql). Acá sólo lectura/escritura.

Key format: ``sha256("{country}:{tool_name}:" + json.dumps(args, sort_keys=True))``.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class _ConnLike(Protocol):
    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> Any: ...


class _PoolLike(Protocol):
    def acquire(self) -> Any: ...


# Backend opcional para testing / boot temprano.
class _MemoryBackend:
    def __init__(self) -> None:
        self._data: dict[str, tuple[dict[str, Any], datetime]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at < datetime.now(UTC):
            del self._data[key]
            return None
        return value

    async def set(self, key: str, value: dict[str, Any], expires_at: datetime) -> None:
        self._data[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)


class ToolCache:
    """Cache asíncrono sobre Postgres (pool asyncpg) con fallback en memoria.

    Si no hay ``pool`` configurado (e.g. tests offline) usa un dict in-memory
    en proceso. Eso evita acoplar todos los tests a Supabase.
    """

    def __init__(
        self,
        pool: _PoolLike | None = None,
        *,
        namespace: str = "tools",
    ) -> None:
        self._pool = pool
        self._namespace = namespace
        self._memory = _MemoryBackend()

    @staticmethod
    def make_key(country: str, tool_name: str, args: dict[str, Any]) -> str:
        """SHA-256 del payload canonicalizado. ``args`` se serializa con
        ``sort_keys`` para que ``{"a":1,"b":2}`` y ``{"b":2,"a":1}`` colisionen."""
        payload = json.dumps(
            args,
            sort_keys=True,
            ensure_ascii=False,
            default=_json_default,
        )
        prefix = f"{country}:{tool_name}:".encode()
        digest = hashlib.sha256(prefix + payload.encode("utf-8")).hexdigest()
        return f"{country}:{tool_name}:{digest}"

    async def get(self, key: str) -> dict[str, Any] | None:
        if self._pool is None:
            return await self._memory.get(key)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value, expires_at FROM tool_cache WHERE key = $1",
                key,
            )
        if row is None:
            return None
        if row["expires_at"] < datetime.now(UTC):
            # expirado; el cleanup horario lo va a barrer, no insistimos.
            return None
        value = row["value"]
        # asyncpg devuelve dict si el codec jsonb está registrado; si no, str.
        if isinstance(value, str):
            value = json.loads(value)
        return value

    async def set(
        self,
        key: str,
        value: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None:
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        if self._pool is None:
            await self._memory.set(key, value, expires_at)
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tool_cache (key, value, expires_at)
                VALUES ($1, $2::jsonb, $3)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    expires_at = EXCLUDED.expires_at
                """,
                key,
                json.dumps(value, ensure_ascii=False, default=_json_default),
                expires_at,
            )

    async def delete(self, key: str) -> None:
        if self._pool is None:
            await self._memory.delete(key)
            return
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM tool_cache WHERE key = $1", key)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"not JSON-serializable: {type(obj).__name__}")


_default_cache: ToolCache | None = None


def get_cache() -> ToolCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = ToolCache(pool=None)
    return _default_cache


def set_cache(cache: ToolCache | None) -> None:
    global _default_cache
    _default_cache = cache


def configure_cache_from_env() -> None:
    """Inicializa pool asyncpg si ``SUPABASE_DB_URL`` está seteada.

    Llamado por el worker en startup. Si falla la conexión, queda con fallback
    in-memory: las tools siguen funcionando, sólo no comparten cache entre
    runs.
    """
    dsn = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        return
    # import diferido para no exigir asyncpg en contextos de testing puro
    import asyncpg  # noqa: PLC0415

    async def _connect() -> None:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
        set_cache(ToolCache(pool=pool))

    # El caller (worker.main) decide cuándo correr este coroutine.
    # Acá sólo dejamos el helper expuesto.
    global _pending_connect
    _pending_connect = _connect  # type: ignore[name-defined]


async def cached_tool_call(  # noqa: UP047  # PEP 695 syntax not supported by all tooling yet
    *,
    country: str,
    tool_name: str,
    args: dict[str, Any],
    ttl_seconds: int,
    output_model: type[T],
    handler: Callable[..., Awaitable[T]],
    cache: ToolCache | None = None,
) -> T:
    """Envuelve un handler async con lectura/escritura de cache.

    - ``args`` debe ser dict serializable (los models Pydantic se pasan a dict
      antes de llamar acá).
    - ``output_model`` se usa para parsear el JSON cacheado al re-hidratar.
    - ``handler`` recibe ``**args`` y retorna una instancia de ``output_model``.
    """
    cache = cache or get_cache()
    key = ToolCache.make_key(country, tool_name, args)

    cached = await cache.get(key)
    if cached is not None:
        return output_model.model_validate(cached)

    result = await handler(**args)
    if not isinstance(result, output_model):
        raise TypeError(
            f"tool {tool_name} returned {type(result).__name__}, expected "
            f"{output_model.__name__}"
        )
    await cache.set(key, result.model_dump(mode="json"), ttl_seconds=ttl_seconds)
    return result
