"""SSE generator: backlog → live → heartbeat → graceful close.

This is the bridge between ``InvestigationListener`` (LISTEN/NOTIFY) and
``sse-starlette``'s ``EventSourceResponse`` (HTTP/1.1 chunked text stream).

Each yielded dict becomes ``id: N\\nevent: type\\ndata: {json}\\n\\n`` on the
wire — sse-starlette handles the framing. The ``id`` field is what the
client echoes back as ``Last-Event-ID`` on reconnect.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from src.sse.events import TERMINAL_EVENT_TYPES, StreamedEvent
from src.sse.listener import InvestigationListener

log = structlog.get_logger(__name__)

DEFAULT_HEARTBEAT_SECONDS = 30.0


def _format_event(event: StreamedEvent) -> dict[str, Any]:
    """Render a StreamedEvent in the dict shape sse-starlette expects.

    The ``payload`` already carries the type discriminator (the worker
    schemas embed it), so the JSON the frontend receives is a clean
    discriminated union — one switch over ``data.type`` narrows it.
    """
    return {
        "id": str(event.id),
        "event": event.type,
        "data": json.dumps(
            {
                "id": event.id,
                "investigation_id": str(event.investigation_id),
                "type": event.type,
                "agent_callsign": event.agent_callsign,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
            },
            separators=(",", ":"),
            default=str,
        ),
    }


def _heartbeat_message() -> dict[str, Any]:
    """Heartbeats are unpersisted and carry no DB id (they're keep-alive).

    Clients can distinguish them via ``event: heartbeat``; the ``data`` is a
    small JSON object so the parser stays uniform.
    """
    return {
        "event": "heartbeat",
        "data": json.dumps(
            {"type": "heartbeat", "ts": datetime.now(UTC).isoformat()},
            separators=(",", ":"),
        ),
    }


async def _is_disconnected(request: Any) -> bool:
    if request is None:
        return False
    try:
        return bool(await request.is_disconnected())
    except Exception:
        return False


async def event_stream(
    pool: Any,
    investigation_id: UUID,
    last_event_id: int = 0,
    *,
    request: Any = None,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE messages for one subscriber until disconnect or terminal event.

    On entry we acquire a dedicated DB connection (raises ``PoolExhaustedError``
    on timeout — caught upstream and turned into 503 + Retry-After). We then:
      1. Replay the backlog (id > last_event_id).
      2. Loop on LISTEN with a ``heartbeat_seconds`` timeout. On wake, SELECT
         the new rows and emit; on timeout, emit a heartbeat.
      3. Stop as soon as a terminal event is emitted or the client disconnects.
    """
    listener = InvestigationListener(pool, investigation_id, last_event_id)
    async with listener:
        # 1) backlog ---------------------------------------------------------
        async for event in listener.replay_backlog():
            yield _format_event(event)
            if event.type in TERMINAL_EVENT_TYPES:
                log.info(
                    "sse.terminal_in_backlog",
                    investigation_id=str(investigation_id),
                    event_type=event.type,
                )
                return
            if await _is_disconnected(request):
                return

        # 2) live ------------------------------------------------------------
        while True:
            if await _is_disconnected(request):
                return

            received = await listener.wait_for_notification(heartbeat_seconds)
            if not received:
                yield _heartbeat_message()
                continue

            for event in await listener.fetch_new():
                yield _format_event(event)
                if event.type in TERMINAL_EVENT_TYPES:
                    log.info(
                        "sse.terminal_event",
                        investigation_id=str(investigation_id),
                        event_type=event.type,
                    )
                    return

            # cooperative yield so we don't starve the event loop on bursts
            await asyncio.sleep(0)
