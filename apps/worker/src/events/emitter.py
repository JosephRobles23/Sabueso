"""EventEmitter — worker-side producer for the investigation event stream.

A thin wrapper around an asyncpg pool that inserts a validated event row into
``investigation_events``. The trigger ``trg_investigation_events_notify``
(see ``infra/supabase/migrations/005_triggers.sql``) emits a NOTIFY on the
``inv_<uuid>`` channel after each insert, which the API's SSE listener picks
up to fan out to connected clients.

Why a class instead of free functions: investigators emit many events with
the same investigation_id; binding it once via the constructor lets call
sites read as ``emitter.emit("claim_created", {...}, agent="el-contador")``.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

import structlog

from src.events.schemas import AgentCallsign, EventType, validate_payload

log = structlog.get_logger(__name__)


@runtime_checkable
class _PoolLike(Protocol):
    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> str: ...


_INSERT_SQL = """
INSERT INTO investigation_events (investigation_id, type, agent_callsign, payload)
VALUES ($1, $2, $3, $4::jsonb)
RETURNING id
"""


class EventEmitter:
    """Emits events for a single investigation.

    The pool is shared with the rest of the worker. Insert volume is low
    (dozens to a few hundred per investigation), so we don't batch.
    """

    def __init__(self, pool: _PoolLike, investigation_id: UUID) -> None:
        self._pool = pool
        self._investigation_id = investigation_id

    @property
    def investigation_id(self) -> UUID:
        return self._investigation_id

    async def emit(
        self,
        event_type: EventType,
        payload: dict[str, Any] | None = None,
        agent_callsign: AgentCallsign | None = None,
    ) -> int:
        """Insert one event. Returns the BIGSERIAL id (== SSE Last-Event-ID).

        The payload is validated against its Pydantic schema before insert;
        a bad payload raises ``ValidationError`` and never reaches the DB.
        """
        clean = validate_payload(event_type, payload or {})
        event_id: int = await self._pool.fetchval(
            _INSERT_SQL,
            self._investigation_id,
            event_type,
            agent_callsign,
            json.dumps(clean),
        )
        log.debug(
            "events.emitted",
            investigation_id=str(self._investigation_id),
            event_id=event_id,
            type=event_type,
            agent=agent_callsign,
        )
        return event_id
