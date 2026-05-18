"""Conditional edges del grafo.

``fan_out`` es el truco arquitectónico de S-06: convierte el plan
generado por Sabueso (lista de PlanStep) en N ejecuciones paralelas de
subagentes, una por step. LangGraph evalúa cada ``Send`` como una nueva
invocación del nodo destino con un override del estado: cada subagente
recibe el estado completo + su ``current_task`` específico.

Si el plan menciona un agente que no existe como nodo en el grafo, se
loggea y se descarta — preferimos perder un subagente a estallar todo
el grafo. (En producción el plan_node ya normaliza los callsigns).
"""

from __future__ import annotations

import logging

from langgraph.types import Send

from .state import INVESTIGATOR_NAMES, InvestigationState

log = logging.getLogger(__name__)


def _normalize_agent(raw: str) -> str:
    """Map LLM-generated agent names to canonical node names.

    Handles: "El Buscador" -> "buscador", "el-buscador" -> "buscador",
             "la-tasadora" -> "tasadora", "La Tasadora" -> "tasadora", etc.
    """
    s = raw.strip().lower().replace("-", " ")
    for prefix in ("el ", "la "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip().replace(" ", "")


def fan_out(state: InvestigationState) -> list[Send]:
    """Emite un Send por cada PlanStep válido. Cada Send va al nodo
    investigador cuyo nombre coincide con ``step["agent"]``."""
    plan = state.get("plan") or []
    sends: list[Send] = []
    known = set(INVESTIGATOR_NAMES)

    for step in plan:
        agent_raw = step.get("agent")
        if not agent_raw:
            continue
        agent = _normalize_agent(agent_raw)
        if agent not in known:
            log.warning("fan_out: unknown agent %r (normalized from %r) in plan, dropping", agent, agent_raw)
            continue
        # Pasamos el state completo + current_task; el reducer add concatena
        # los claims/edges/events que cada rama produzca.
        payload = {**state, "current_task": step}
        sends.append(Send(agent, payload))

    return sends
