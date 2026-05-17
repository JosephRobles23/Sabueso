from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from src.db.pool import PoolLike
from src.models.entity import Country
from src.models.investigation import Investigation


class InvestigationRepo:
    def __init__(self, pool: PoolLike) -> None:
        self._pool = pool

    async def create(
        self,
        *,
        target_entity_id: UUID,
        country: Country,
        locale: str,
        user_id: UUID | None,
    ) -> UUID:
        """INSERT a pending investigation. Returns the new id."""
        new_id = await self._pool.fetchval(
            """
            INSERT INTO investigations (target_entity_id, country, locale, user_id, status)
            VALUES ($1, $2, $3, $4, 'pending')
            RETURNING id
            """,
            target_entity_id,
            country,
            locale,
            user_id,
        )
        if new_id is None:
            raise RuntimeError("INSERT investigations RETURNING returned no row")
        return UUID(str(new_id))

    async def get(self, investigation_id: UUID) -> Investigation | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, target_entity_id, country, locale, status, plan, dossier_md,
                   cost_usd, progress_pct, is_public, started_at, finished_at
            FROM investigations
            WHERE id = $1
            """,
            investigation_id,
        )
        if not row:
            return None
        data: dict[str, Any] = dict(row)
        plan = data.get("plan")
        if isinstance(plan, str):
            data["plan"] = json.loads(plan)
        elif plan is None:
            data["plan"] = []
        return Investigation.model_validate(data)

    async def enqueue(self, investigation_id: UUID, queue: str) -> None:
        """Push to pgmq. Best-effort: failures here are surfaced to the caller."""
        await self._pool.execute(
            "SELECT pgmq.send($1, $2::jsonb)",
            queue,
            json.dumps({"investigation_id": str(investigation_id)}),
        )
