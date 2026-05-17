"""InvestigationState — TypedDict del grafo LangGraph (C4 §6.1).

Los campos acumulativos (`claims`, `edges`, `events`) usan
``Annotated[list, operator.add]`` para que LangGraph los concatene cuando
varias ramas paralelas (Send fan-out a subagentes) emiten updates al mismo
canal. Los otros campos son "last-write-wins" — el último escritor gana.

Las claves de runtime que no son parte del contrato del C4 (`entity`,
`history`, `current_task`, `status`, `user_query`) están marcadas como
``NotRequired`` para que se puedan omitir al construir el estado inicial.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, NotRequired, TypedDict

Country = Literal["pe", "cl", "mx", "sv"]
InvestigationStatus = Literal[
    "pending",
    "planning",
    "running",
    "verifying",
    "synthesizing",
    "complete",
    "failed",
    "cancelled",
]


class PlanStep(TypedDict, total=False):
    agent: str
    task: str
    priority: int


class InvestigationState(TypedDict, total=False):
    # ---- identidad / contexto ------------------------------------------------
    investigation_id: str
    target_entity_id: str
    country: Country
    locale: str
    user_query: NotRequired[str]

    # ---- plan generado por Sabueso ------------------------------------------
    plan: list[PlanStep]

    # ---- canales acumulativos (Annotated[..., add] = LangGraph reducer) -----
    claims: Annotated[list[dict[str, Any]], add]
    edges: Annotated[list[dict[str, Any]], add]
    events: Annotated[list[dict[str, Any]], add]

    # ---- MoA verifier --------------------------------------------------------
    verified_claims: list[dict[str, Any]]

    # ---- output del orquestador ---------------------------------------------
    dossier_md: str

    # ---- contabilidad --------------------------------------------------------
    started_at: str
    cost_usd: float
    token_usage: dict[str, Any]

    # ---- runtime (no es parte del contrato C4, lo escriben nodos internos) ---
    entity: NotRequired[dict[str, Any]]
    history: NotRequired[list[dict[str, Any]]]
    current_task: NotRequired[PlanStep]
    status: NotRequired[InvestigationStatus]


# Plan por defecto: 6 investigadores con tareas genéricas. Se usa cuando
# Sabueso falla 2 veces seguidas al generar JSON parseable.
DEFAULT_PLAN: list[PlanStep] = [
    {"agent": "buscador", "task": "Identificar entidad y aliases", "priority": 1},
    {"agent": "contador", "task": "Rastrear contratos públicos", "priority": 2},
    {"agent": "tasadora", "task": "Cruzar patrimonio declarado", "priority": 3},
    {"agent": "letrado", "task": "Buscar leyes votadas y sentencias", "priority": 4},
    {"agent": "detective", "task": "Mapear familia, socios, directorios", "priority": 5},
    {"agent": "periodista", "task": "Revisar archivos de prensa", "priority": 6},
]


# Nombres canónicos de los nodos investigador en el grafo. Mantener en
# sync con `placeholders.INVESTIGATOR_NODES` y los handlers de S-10/S-11.
INVESTIGATOR_NAMES: tuple[str, ...] = (
    "buscador",
    "tasadora",
    "contador",
    "letrado",
    "detective",
    "periodista",
)


# Mapeo de callsign corto (usado en nodos) a callsign extendido (usado en
# eventos / AgentCallsign literal de events/schemas.py).
CALLSIGN_TO_EVENT_AGENT: dict[str, str] = {
    "sabueso": "sabueso",
    "buscador": "el-buscador",
    "tasadora": "la-tasadora",
    "contador": "el-contador",
    "letrado": "el-letrado",
    "detective": "el-detective",
    "periodista": "el-periodista",
    "jueza": "la-jueza",
}


def event_agent_for(callsign: str) -> str:
    """Mapea callsign corto al literal usado en investigation_events."""
    return CALLSIGN_TO_EVENT_AGENT.get(callsign, callsign)
