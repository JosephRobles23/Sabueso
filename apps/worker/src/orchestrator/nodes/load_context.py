"""Nodo 1: load_context — fetch entity + historial reciente.

Lee la fila de ``entities`` que corresponde al target_entity_id y los
últimos N claims emitidos contra esa entidad en investigaciones previas.
Esto alimenta el prompt de Sabueso con contexto histórico ("ya
investigamos X en marzo, encontramos Y") sin tener que re-descubrirlo.

Si no hay pool de DB disponible (tests unitarios), retorna entity/history
vacíos para no romper el flujo.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from ..state import InvestigationState

_Node = Callable[[InvestigationState], Awaitable[dict[str, Any]]]

log = logging.getLogger(__name__)

ENTITY_SQL = """
SELECT id, country, type, identifier, name, aliases, metadata
FROM entities
WHERE id = $1
"""

HISTORY_SQL = """
SELECT c.id, c.predicate, c.object_value, c.confidence, c.agent_callsign,
       c.created_at, c.investigation_id
FROM claims c
WHERE c.entity_id = $1
ORDER BY c.created_at DESC
LIMIT $2
"""

DEFAULT_HISTORY_LIMIT = 20


class _PoolLike(Protocol):
    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def fetch(self, query: str, *args: Any) -> Any: ...


@dataclass
class LoadContextDeps:
    pool: _PoolLike | None = None
    history_limit: int = DEFAULT_HISTORY_LIMIT


def make_load_context_node(deps: LoadContextDeps) -> _Node:
    async def load_context(state: InvestigationState) -> dict[str, Any]:
        entity: dict[str, Any] = {}
        history: list[dict[str, Any]] = []
        target_id = state.get("target_entity_id")
        if deps.pool is not None and target_id:
            try:
                row = await deps.pool.fetchrow(ENTITY_SQL, target_id)
                if row:
                    entity = dict(row)
                rows = await deps.pool.fetch(HISTORY_SQL, target_id, deps.history_limit)
                history = [dict(r) for r in rows]
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("load_context.db_error: %s", exc)

        started_at = state.get("started_at") or datetime.now(UTC).isoformat()

        return {
            "entity": entity,
            "history": history,
            "status": "planning",
            "started_at": started_at,
            "events": [
                {
                    "type": "investigation_started",
                    "agent": "sabueso",
                    "payload": {
                        "investigation_id": state.get("investigation_id"),
                        "entity_id": target_id,
                        "country": state.get("country"),
                        "locale": state.get("locale", "es"),
                    },
                }
            ],
        }

    return load_context
