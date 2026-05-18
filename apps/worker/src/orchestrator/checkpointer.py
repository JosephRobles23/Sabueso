"""Factories de checkpointer LangGraph.

Producción: ``open_postgres_checkpointer(DB_URL)`` abre un
``PostgresSaver`` apuntado a Supabase. Es un context manager porque el
saver mantiene una conexión psycopg abierta para todo el ciclo de vida
del grafo; el caller (worker entrypoint en S-07) hace ``with
open_postgres_checkpointer(...) as saver:`` y le pasa el saver a
``build_graph``.

El método ``setup()`` crea las tablas ``checkpoints``,
``checkpoint_writes``, ``checkpoint_blobs`` en el schema configurado en la
primera invocación; es idempotente.

Tests: ``in_memory_checkpointer()`` retorna un ``InMemorySaver`` que
satisface el mismo protocolo y cuenta checkpoints por ``thread_id`` vía
``saver.list({"configurable": {"thread_id": ...}})``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver


@contextmanager
def open_postgres_checkpointer(
    conn_string: str | None = None,
    *,
    setup: bool = True,
) -> Iterator[Any]:
    """Yield un PostgresSaver listo para usarse, ejecutando setup() en la
    primera corrida (crea las tablas de checkpoint en Supabase).

    Si ``conn_string`` es None se lee de ``SUPABASE_DB_URL`` o ``DATABASE_URL``.
    """
    from langgraph.checkpoint.postgres import PostgresSaver  # noqa: PLC0415

    conn = conn_string or os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not conn:
        raise RuntimeError(
            "open_postgres_checkpointer requires SUPABASE_DB_URL or DATABASE_URL"
        )

    with PostgresSaver.from_conn_string(conn) as saver:
        if setup:
            saver.setup()
        yield saver


@asynccontextmanager
async def open_async_postgres_checkpointer(
    conn_string: str | None = None,
    *,
    setup: bool = True,
) -> AsyncIterator[Any]:
    """Async version: yields an AsyncPostgresSaver for use with ainvoke."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: PLC0415

    conn = conn_string or os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not conn:
        raise RuntimeError(
            "open_async_postgres_checkpointer requires SUPABASE_DB_URL or DATABASE_URL"
        )

    async with AsyncPostgresSaver.from_conn_string(conn) as saver:
        if setup:
            await saver.setup()
        yield saver


def in_memory_checkpointer() -> BaseCheckpointSaver[Any]:
    """Checkpointer para tests: InMemorySaver con la misma API que el de Postgres."""
    from langgraph.checkpoint.memory import InMemorySaver  # noqa: PLC0415

    return InMemorySaver()
