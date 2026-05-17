from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from src.db.pool import PoolLike
from src.models.investigator_config import InvestigatorConfig


class InvestigatorConfigRepo:
    """CRUD sobre investigator_configs. RLS en DB asegura que cada user solo
    ve/edita lo suyo cuando se conecta con su JWT; el API corre con
    service_role así que igual filtra explícitamente por user_id."""

    def __init__(self, pool: PoolLike) -> None:
        self._pool = pool

    async def list_for_user(self, user_id: UUID) -> list[InvestigatorConfig]:
        rows = await self._pool.fetch(
            """
            SELECT user_id, callsign, config, created_at, updated_at
            FROM investigator_configs
            WHERE user_id = $1
            ORDER BY callsign
            """,
            user_id,
        )
        return [InvestigatorConfig.model_validate(_normalize(r)) for r in rows]

    async def patch(
        self,
        user_id: UUID,
        callsign: str,
        partial: dict[str, Any],
    ) -> InvestigatorConfig | None:
        """Shallow merge JSONB via `||`. Hace UPSERT para cubrir el caso de
        users creados antes de 010 (cuyas filas default nunca se sembraron)
        — sin esto un PATCH temprano devolvería 404 sin razón visible."""
        row = await self._pool.fetchrow(
            """
            INSERT INTO investigator_configs (user_id, callsign, config)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (user_id, callsign) DO UPDATE
                SET config = investigator_configs.config || EXCLUDED.config,
                    updated_at = now()
            RETURNING user_id, callsign, config, created_at, updated_at
            """,
            user_id,
            callsign,
            json.dumps(partial),
        )
        return InvestigatorConfig.model_validate(_normalize(row)) if row else None


def _normalize(row: Any) -> dict[str, Any]:
    data = dict(row)
    data["config"] = data.get("config") or {}
    return data
