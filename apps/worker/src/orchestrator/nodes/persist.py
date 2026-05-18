"""Nodo 7: persist — UPDATE investigations + INSERT claims/edges en una transacción.

Garantía: o se persiste todo (status='complete', dossier, claims, edges) o
no se persiste nada (rollback). Si el INSERT de un solo claim falla, la
transacción entera se revierte y el estado en DB queda como estaba antes
del nodo. Esto evita dossiers "fantasma" sin sus claims, o claims sin su
investigación marcada como completa.

El nodo es idempotente a nivel de investigation (UPDATE con WHERE id=?),
pero los INSERT de claims/edges no — re-ejecutar este nodo después de un
éxito duplicaría filas. La protección está aguas arriba en pgmq
(visibility_timeout + dedupe por ack id).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from ..state import InvestigationState

_Node = Callable[[InvestigationState], Awaitable[dict[str, Any]]]

log = logging.getLogger(__name__)


UPDATE_INVESTIGATION_SQL = """
UPDATE investigations
SET status = $2,
    plan = $3::jsonb,
    dossier_md = $4,
    cost_usd = $5,
    token_usage = $6::jsonb,
    progress_pct = $7,
    finished_at = now()
WHERE id = $1
"""

INSERT_CLAIM_SQL = """
INSERT INTO claims (
    id, investigation_id, entity_id, predicate, object_value,
    source_id, source_extract, source_hash, confidence, agent_callsign,
    verified_by_jueza, verified_at
)
VALUES (
    coalesce($1, uuid_generate_v4()), $2, $3, $4, $5::jsonb,
    $6, $7, $8, $9, $10,
    $11, $12
)
ON CONFLICT DO NOTHING
"""

INSERT_EDGE_SQL = """
INSERT INTO edges (
    id, investigation_id, from_entity, to_entity, type,
    weight, confidence, evidence_claims, agent_callsign
)
VALUES (
    coalesce($1, uuid_generate_v4()), $2, $3, $4, $5,
    $6, $7, $8, $9
)
ON CONFLICT (from_entity, to_entity, type) DO NOTHING
"""


class _ConnLike(Protocol):
    async def execute(self, query: str, *args: Any) -> str: ...

    def transaction(self) -> Any: ...


class _PoolLike(Protocol):
    def acquire(self) -> Any: ...


@dataclass
class PersistDeps:
    pool: _PoolLike | None = None
    # Si se setea, el nodo nunca toca la DB y sólo emite los eventos +
    # status; útil para tests donde queremos verificar el flujo sin Postgres.
    dry_run: bool = False


def make_persist_node(deps: PersistDeps) -> _Node:
    async def persist(state: InvestigationState) -> dict[str, Any]:
        investigation_id = state.get("investigation_id")
        claims = state.get("claims") or []
        edges = state.get("edges") or []
        dossier = state.get("dossier_md") or ""
        plan = state.get("plan") or []
        cost = float(state.get("cost_usd") or 0.0)
        token_usage = state.get("token_usage") or {}

        if deps.dry_run or deps.pool is None or not investigation_id:
            log.info(
                "persist.dry_run investigation_id=%s claims=%d edges=%d",
                investigation_id,
                len(claims),
                len(edges),
            )
            return _success_delta(investigation_id, claims, edges, cost)

        target_entity_id = state.get("target_entity_id")

        try:
            async with _acquire(deps.pool) as conn:
                async with conn.transaction():
                    await conn.execute(
                        UPDATE_INVESTIGATION_SQL,
                        investigation_id,
                        "complete",
                        json.dumps(plan),
                        dossier,
                        cost,
                        json.dumps(token_usage),
                        100,
                    )
                    skipped = 0
                    for c in claims:
                        entity_id = c.get("entity_id") or target_entity_id
                        predicate = c.get("predicate")
                        if not entity_id or not predicate or not c.get("source_id"):
                            skipped += 1
                            continue
                        await conn.execute(
                            INSERT_CLAIM_SQL,
                            c.get("id"),
                            investigation_id,
                            entity_id,
                            predicate,
                            json.dumps(c.get("object_value") or {}),
                            c.get("source_id"),
                            c.get("source_extract"),
                            c.get("source_hash"),
                            c.get("confidence"),
                            c.get("agent_callsign") or c.get("agent"),
                            bool(c.get("verified_by_jueza", False)),
                            c.get("verified_at"),
                        )
                    if skipped:
                        log.warning("persist.skipped_claims: %d claims missing required fields", skipped)
                    for e in edges:
                        await conn.execute(
                            INSERT_EDGE_SQL,
                            e.get("id"),
                            investigation_id,
                            e.get("from_entity"),
                            e.get("to_entity"),
                            e.get("type"),
                            float(e.get("weight", 1.0)),
                            e.get("confidence"),
                            e.get("evidence_claims") or [],
                            e.get("agent_callsign") or e.get("agent"),
                        )
        except Exception as exc:
            log.exception("persist.transaction_failed: %s", exc)
            # Rollback automático al salir del context manager con excepción.
            return {
                "status": "failed",
                "events": [
                    {
                        "type": "investigation_failed",
                        "agent": "sabueso",
                        "payload": {
                            "error": f"persist_failed: {exc}",
                            "partial_claims": len(claims),
                        },
                    }
                ],
            }

        return _success_delta(investigation_id, claims, edges, cost)

    return persist


def _success_delta(
    investigation_id: str | None,
    claims: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    cost: float,
) -> dict[str, Any]:
    return {
        "status": "complete",
        "events": [
            {
                "type": "investigation_complete",
                "agent": "sabueso",
                "payload": {
                    "investigation_id": investigation_id,
                    "total_claims": len(claims),
                    "total_cost_usd": round(cost, 4),
                    "edges_count": len(edges),
                },
            }
        ],
    }


@asynccontextmanager
async def _acquire(pool: _PoolLike) -> AsyncIterator[Any]:
    """Adapta pool.acquire() para que funcione con asyncpg real o mocks
    que devuelven directamente un async context manager."""
    cm = pool.acquire()
    if hasattr(cm, "__aenter__"):
        async with cm as conn:
            yield conn
    else:
        # algunos mocks devuelven la conexión directamente
        yield cm
