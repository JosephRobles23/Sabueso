"""Placeholder nodes para los 6 investigadores + La Jueza.

S-06 sólo arma el cableado del grafo. Las implementaciones concretas
viven en S-10 (investigators) y S-11 (jueza_moa).

Cada nodo investigador acepta el state con ``current_task`` ya seteado
(lo inyectó ``fan_out`` vía ``Send``). Si hay un ``runner`` registrado
en ``investigator_runners[callsign]`` lo invoca; si no, emite un evento
placeholder y retorna sin claims. Esto permite testear el grafo end-to-end
mock-eando 1 solo investigador.

El runner debe respetar la interfaz:

    async def runner(task: dict, state: dict) -> dict
        -> {"claims": [...], "edges": [...], "events": [...]}

o equivalentemente puede retornar sólo ``list[dict]`` (sólo claims). Se
acepta ambos para que los runners reales (``BaseInvestigator.run``) que
devuelven una lista de claims encajen sin wrapper.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from ..state import InvestigationState, event_agent_for

log = logging.getLogger(__name__)

InvestigatorRunner = Callable[[dict[str, Any], dict[str, Any]], Awaitable[Any]]
_Node = Callable[[InvestigationState], Awaitable[dict[str, Any]]]


def make_investigator_node(callsign: str, runner: InvestigatorRunner | None) -> _Node:
    async def investigator_node(state: InvestigationState) -> dict[str, Any]:
        task: dict[str, Any] = dict(state.get("current_task") or {})
        event_agent = event_agent_for(callsign)
        started_event = {
            "type": "agent_started",
            "agent": event_agent,
            "payload": {"task": task.get("task", "")},
        }

        if runner is None:
            log.warning("investigator.%s: no runner registered, emitting empty claims", callsign)
            return {
                "claims": [],
                "edges": [],
                "events": [
                    started_event,
                    {
                        "type": "agent_finished",
                        "agent": event_agent,
                        "payload": {"claims_created": 0, "cost_usd": 0.0, "duration_ms": 0},
                    },
                ],
            }

        try:
            result = await runner(task, dict(state))
        except Exception as exc:
            log.exception("investigator.%s.error: %s", callsign, exc)
            return {
                "claims": [],
                "edges": [],
                "events": [
                    started_event,
                    {
                        "type": "agent_error",
                        "agent": event_agent,
                        "payload": {"error": str(exc)},
                    },
                ],
            }

        claims, edges, events = _normalize_result(result, event_agent)
        finished_event = {
            "type": "agent_finished",
            "agent": event_agent,
            "payload": {
                "claims_created": len(claims),
                "cost_usd": float(state.get("cost_usd") or 0.0),
                "duration_ms": 0,
            },
        }
        return {
            "claims": claims,
            "edges": edges,
            "events": [started_event, *events, finished_event],
        }

    return investigator_node


def make_jueza_node(runner: InvestigatorRunner | None = None) -> _Node:
    """Placeholder de La Jueza (S-11). Si no hay runner, pasa los claims
    como verified_claims y emite verification_done con score=1.0."""

    async def jueza_node(state: InvestigationState) -> dict[str, Any]:
        claims = state.get("claims") or []
        if runner is None:
            verified = [
                {**c, "verified_by_jueza": True, "verifier_score": 1.0}
                for c in claims
            ]
            events = [
                {
                    "type": "verification_done",
                    "agent": "la-jueza",
                    "payload": {
                        "claim_id": c.get("id"),
                        "verified": True,
                        "verifier_score": 1.0,
                    },
                }
                for c in claims
            ]
            return {
                "verified_claims": verified,
                "events": events,
            }

        try:
            result = await runner({"verify_all": True}, dict(state))
        except Exception as exc:
            log.exception("jueza.error: %s", exc)
            return {
                "verified_claims": list(claims),
                "events": [
                    {
                        "type": "agent_error",
                        "agent": "la-jueza",
                        "payload": {"error": str(exc)},
                    }
                ],
            }

        verified, _, events = _normalize_result(result, "la-jueza")
        return {
            "verified_claims": verified or list(claims),
            "events": events,
        }

    return jueza_node


def _normalize_result(
    result: Any,
    event_agent: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Acepta dict {claims, edges, events} o lista plana de claims."""
    if isinstance(result, list):
        return [_stamp_agent(c, event_agent) for c in result], [], []
    if isinstance(result, dict):
        claims = [_stamp_agent(c, event_agent) for c in (result.get("claims") or [])]
        edges = list(result.get("edges") or [])
        events = list(result.get("events") or [])
        return claims, edges, events
    return [], [], []


def _stamp_agent(claim: dict[str, Any], event_agent: str) -> dict[str, Any]:
    if "agent_callsign" not in claim:
        claim = {**claim, "agent_callsign": event_agent}
    return claim
