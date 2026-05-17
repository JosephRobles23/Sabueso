from __future__ import annotations

from typing import Any
from uuid import UUID

from src.db.pool import PoolLike


class ClaimRepo:
    """Read-only access to claims for entity drilldown views.

    Writes happen in the worker (S-07+) inside an atomic transaction.
    """

    def __init__(self, pool: PoolLike) -> None:
        self._pool = pool

    async def list_for_entity(self, entity_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT id, predicate, object_value, source_id, source_extract,
                   confidence, agent_callsign, verified_by_jueza, created_at
            FROM claims
            WHERE entity_id = $1 AND superseded_by IS NULL
            ORDER BY created_at DESC
            LIMIT $2
            """,
            entity_id,
            limit,
        )
        return [dict(r) for r in rows]
