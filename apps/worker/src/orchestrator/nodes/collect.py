"""Nodo 4: collect — barrier después del fan-out.

Cuando todos los Send() emitidos por ``fan_out`` terminan, LangGraph
converge en ``collect``. El reducer ``Annotated[list, add]`` ya juntó los
claims/edges/events de cada rama; este nodo sólo marca la transición de
estado a 'verifying' y emite un evento agregado de telemetría.

No filtra ni deduplica claims — eso es trabajo de La Jueza (S-11).
"""

from __future__ import annotations

from typing import Any

from ..state import InvestigationState


def collect_claims(state: InvestigationState) -> dict[str, Any]:
    claims = state.get("claims") or []
    edges = state.get("edges") or []
    return {
        "status": "verifying",
        "events": [
            {
                "type": "synthesis_started",
                "agent": "sabueso",
                "payload": {"claim_count": len(claims)},
                "edges_count": len(edges),
            }
        ],
    }
