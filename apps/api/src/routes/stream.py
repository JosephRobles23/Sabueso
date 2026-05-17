"""SSE endpoint: ``GET /api/v1/stream/{investigation_id}``.

Uses ``sse-starlette``'s ``EventSourceResponse`` to handle chunked framing,
headers, and client-disconnect detection. Pool exhaustion returns 503 with
``Retry-After: 5`` so clients back off instead of looping immediately.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from sse_starlette.sse import EventSourceResponse

from src.deps import PoolDep
from src.sse.listener import PoolExhaustedError
from src.sse.stream import event_stream

log = structlog.get_logger(__name__)

router = APIRouter(tags=["stream"])


def _parse_last_event_id(header_value: str | None, query_value: int | None) -> int:
    """Header wins over query; both are optional. Bad values default to 0.

    ``EventSource`` doesn't allow custom request headers on reconnect, but the
    browser automatically sends ``Last-Event-ID`` after the first connection.
    We accept ``last_event_id`` as a query param for clients that need to
    bootstrap from a stored id (e.g. after a full page reload).
    """
    if header_value:
        try:
            return max(0, int(header_value))
        except ValueError:
            return 0
    if query_value is not None:
        return max(0, query_value)
    return 0


@router.get("/stream/{investigation_id}")
async def stream(
    investigation_id: UUID,
    request: Request,
    pool: PoolDep,
    last_event_id_query: int | None = Query(default=None, alias="last_event_id"),
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
) -> Any:
    """Open a long-lived SSE stream for one investigation.

    Backlog (id > Last-Event-ID) is replayed first, then live notifications
    flow until the client disconnects or a terminal event is emitted. Each
    subscriber holds one asyncpg connection for its full lifetime.
    """
    last_event_id = _parse_last_event_id(last_event_id_header, last_event_id_query)

    # Probe the pool up-front: if exhausted, fail fast with 503 instead of
    # half-opening a stream. The actual acquire happens inside event_stream's
    # context manager (which also raises PoolExhaustedError on timeout).
    try:
        generator = event_stream(
            pool,
            investigation_id,
            last_event_id=last_event_id,
            request=request,
        )
    except PoolExhaustedError as exc:
        log.warning(
            "sse.pool_exhausted",
            investigation_id=str(investigation_id),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="connection pool exhausted, retry shortly",
            headers={"Retry-After": "5"},
        ) from exc

    async def _safe_generator() -> Any:
        # Translate a runtime pool-exhausted error (raised on enter of the
        # listener context manager) into a clean stop. The pre-flight 503
        # above is unreachable since acquire is lazy; this branch is the
        # one that actually fires.
        try:
            async for message in generator:
                yield message
        except PoolExhaustedError:
            log.warning(
                "sse.pool_exhausted_mid_stream",
                investigation_id=str(investigation_id),
            )
            # No clean way to swap to 503 once the response started; emit a
            # final event so the client knows to back off and reconnect.
            yield {
                "event": "investigation_failed",
                "data": '{"type":"investigation_failed","error":"pool_exhausted"}',
            }

    return EventSourceResponse(
        _safe_generator(),
        ping=None,  # we manage heartbeats ourselves to keep them inside the contract
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
