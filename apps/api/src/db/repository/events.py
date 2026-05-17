from __future__ import annotations

from typing import Any
from uuid import UUID

from src.db.pool import PoolLike


class EventRepo:
    """Read access to investigation_events, used by SSE replay (S-08)."""

    def __init__(self, pool: PoolLike) -> None:
        self._pool = pool

    async def list_since(
        self,
        investigation_id: UUID,
        last_event_id: int = 0,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT id, investigation_id, type, agent_callsign, payload, created_at
            FROM investigation_events
            WHERE investigation_id = $1 AND id > $2
            ORDER BY id ASC
            LIMIT $3
            """,
            investigation_id,
            last_event_id,
            limit,
        )
        return [dict(r) for r in rows]
