"""Per-subscriber LISTEN/NOTIFY bridge.

Each SSE client gets one ``InvestigationListener`` that holds a dedicated
asyncpg connection from the pool, LISTENs on the investigation's channel,
and exposes an async iterator of new event rows (replaying the backlog
first if ``last_event_id`` is set).

Lifecycle: ``async with listener: async for evt in listener.stream(): ...``
On exit, the LISTEN is unregistered and the connection returns to the pool.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

import structlog

from src.sse.events import StreamedEvent, sanitize_channel

log = structlog.get_logger(__name__)


class PoolExhaustedError(Exception):
    """The asyncpg pool couldn't hand out a connection in time.

    Routed by the API to a 503 + ``Retry-After: 5`` so the client backs off
    instead of hammering us further.
    """


@runtime_checkable
class _ConnectionLike(Protocol):
    async def add_listener(self, channel: str, callback: Any) -> None: ...
    async def remove_listener(self, channel: str, callback: Any) -> None: ...
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...


@runtime_checkable
class _PoolWithAcquire(Protocol):
    def acquire(self, *, timeout: float | None = ...) -> Any: ...


_BACKLOG_SQL = """
SELECT id, investigation_id, type, agent_callsign, payload, created_at
FROM investigation_events
WHERE investigation_id = $1 AND id > $2
ORDER BY id ASC
LIMIT $3
"""


class InvestigationListener:
    """Bridge a Postgres LISTEN channel into an async iterator of events.

    Caller owns the lifecycle: ``async with`` to acquire/release the
    dedicated connection; ``async for`` to consume events.
    """

    def __init__(
        self,
        pool: Any,
        investigation_id: UUID,
        last_event_id: int = 0,
        *,
        acquire_timeout: float = 2.0,
        backlog_chunk: int = 500,
    ) -> None:
        self._pool = pool
        self._investigation_id = investigation_id
        self._last_event_id = last_event_id
        self._acquire_timeout = acquire_timeout
        self._backlog_chunk = backlog_chunk
        self._channel = sanitize_channel(investigation_id)
        self._queue: asyncio.Queue[None] = asyncio.Queue()
        self._conn_cm: Any = None
        self._conn: _ConnectionLike | None = None

    @property
    def last_event_id(self) -> int:
        return self._last_event_id

    @property
    def channel(self) -> str:
        return self._channel

    async def __aenter__(self) -> InvestigationListener:
        try:
            self._conn_cm = self._pool.acquire(timeout=self._acquire_timeout)
            self._conn = await self._conn_cm.__aenter__()
        except TimeoutError as exc:
            log.warning(
                "sse.pool_exhausted",
                investigation_id=str(self._investigation_id),
            )
            raise PoolExhaustedError("asyncpg pool exhausted") from exc

        assert self._conn is not None
        await self._conn.add_listener(self._channel, self._on_notify)
        log.debug(
            "sse.listener_attached",
            investigation_id=str(self._investigation_id),
            channel=self._channel,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._conn is not None:
            with contextlib.suppress(Exception):
                await self._conn.remove_listener(self._channel, self._on_notify)
        if self._conn_cm is not None:
            with contextlib.suppress(Exception):
                await self._conn_cm.__aexit__(exc_type, exc, tb)
        self._conn = None
        self._conn_cm = None
        log.debug(
            "sse.listener_detached",
            investigation_id=str(self._investigation_id),
            channel=self._channel,
        )

    def _on_notify(self, *_args: Any, **_kwargs: Any) -> None:
        """asyncpg listener callback. Signature: (conn, pid, channel, payload).

        We only use it as a wakeup signal; the actual rows come from a fresh
        SELECT, which keeps us robust to NOTIFY coalescing and the 8000-byte
        payload limit. ``put_nowait`` is safe: the queue is unbounded.
        """
        self._queue.put_nowait(None)

    async def replay_backlog(self) -> AsyncIterator[StreamedEvent]:
        """Yield any rows the client already missed (id > last_event_id).

        Chunked so a very long-running investigation doesn't load thousands
        of rows in a single query.
        """
        assert self._conn is not None
        while True:
            rows = await self._conn.fetch(
                _BACKLOG_SQL,
                self._investigation_id,
                self._last_event_id,
                self._backlog_chunk,
            )
            if not rows:
                return
            for row in rows:
                event = StreamedEvent.from_row(dict(row))
                self._last_event_id = event.id
                yield event
            if len(rows) < self._backlog_chunk:
                return

    async def wait_for_notification(self, timeout: float) -> bool:
        """Block until a NOTIFY arrives or ``timeout`` elapses.

        Returns True if a notification was received, False on timeout (caller
        can then emit a heartbeat). Drains all pending wakeups in one go so
        a burst doesn't trigger N redundant SELECTs.
        """
        try:
            await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return False
        while not self._queue.empty():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
        return True

    async def fetch_new(self) -> list[StreamedEvent]:
        """Return events inserted after ``last_event_id``, in order."""
        assert self._conn is not None
        rows = await self._conn.fetch(
            _BACKLOG_SQL,
            self._investigation_id,
            self._last_event_id,
            self._backlog_chunk,
        )
        out: list[StreamedEvent] = []
        for row in rows:
            event = StreamedEvent.from_row(dict(row))
            self._last_event_id = event.id
            out.append(event)
        return out
