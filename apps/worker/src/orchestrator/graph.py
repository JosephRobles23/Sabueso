"""build_graph — factoría del orquestador LangGraph completo.

Topología (C4 §6.1):

    START
      ↓
    load_context  ← fetch entity + history
      ↓
    plan          ← Sabueso (Sonnet 4.6, 4 cache breakpoints)
      ↓ (fan_out conditional edge → N Send)
    [buscador | tasadora | contador | letrado | detective | periodista]
      ↓ (cada subagente)
    collect       ← barrier, reduce claims/edges/events
      ↓
    jueza         ← MoA verifier (placeholder en S-06, real en S-11)
      ↓
    synthesize    ← Sabueso (Opus 4.7, dossier markdown)
      ↓
    persist       ← UPDATE investigations + INSERT claims/edges (transacción)
      ↓
    END

Las dependencias externas (LLM, DB pool, investigator runners,
checkpointer) se inyectan vía ``GraphDeps`` para que los tests puedan
proveer mocks. El test integración de S-06 usa un solo runner real
mockeado, todos los otros investigadores corren como placeholders.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from langgraph.graph import END, START, StateGraph

from ..llm.client import LLMClient
from ..prompts.loader import PromptLoader
from .checkpointer import in_memory_checkpointer
from .edges import fan_out
from .nodes import (
    LoadContextDeps,
    PersistDeps,
    PlanDeps,
    SynthesizeDeps,
    collect_claims,
    make_investigator_node,
    make_jueza_node,
    make_load_context_node,
    make_persist_node,
    make_plan_node,
    make_synthesize_node,
)
from .nodes.placeholders import InvestigatorRunner
from .state import INVESTIGATOR_NAMES, InvestigationState

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.pregel import Pregel


@dataclass
class GraphDeps:
    """Container de dependencias para construir el grafo.

    Todos los campos tienen defaults razonables para tests; producción
    los reemplaza con los reales en el worker entrypoint (S-07).
    """

    llm: LLMClient
    db_pool: Any | None = None
    investigator_runners: dict[str, InvestigatorRunner] = field(default_factory=dict)
    jueza_runner: InvestigatorRunner | None = None
    prompt_loader: PromptLoader | None = None
    plan_model: str = "anthropic/claude-sonnet-4.6"
    synth_model: str = "anthropic/claude-opus-4.7"
    history_limit: int = 20
    persist_dry_run: bool = False


def build_graph(
    deps: GraphDeps,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Pregel[Any, Any, Any, Any]:
    """Construye y compila el grafo. Si no se pasa checkpointer, usa
    InMemorySaver (útil para tests). En producción, el caller pasa un
    PostgresSaver vía ``open_postgres_checkpointer``."""
    if checkpointer is None:
        checkpointer = in_memory_checkpointer()

    loader = deps.prompt_loader or PromptLoader()

    load_context = make_load_context_node(
        LoadContextDeps(pool=deps.db_pool, history_limit=deps.history_limit)
    )
    sabueso_plan = make_plan_node(
        PlanDeps(llm=deps.llm, prompt_loader=loader, plan_model=deps.plan_model)
    )
    synthesize = make_synthesize_node(
        SynthesizeDeps(llm=deps.llm, synth_model=deps.synth_model)
    )
    persist = make_persist_node(
        PersistDeps(pool=deps.db_pool, dry_run=deps.persist_dry_run)
    )
    jueza = make_jueza_node(deps.jueza_runner)

    # LangGraph's add_node generic inference doesn't compose well with
    # mypy strict + async closures; we cast to Any here. Runtime
    # correctness is covered by tests/test_graph_integration.py.
    g = cast(Any, StateGraph(InvestigationState))
    g.add_node("load_context", load_context)
    g.add_node("plan", sabueso_plan)
    g.add_node("collect", collect_claims)
    g.add_node("jueza", jueza)
    g.add_node("synthesize", synthesize)
    g.add_node("persist", persist)

    for agent_name in INVESTIGATOR_NAMES:
        runner = deps.investigator_runners.get(agent_name)
        g.add_node(agent_name, make_investigator_node(agent_name, runner))

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "plan")

    # Fan-out: el plan dispara N Sends (uno por step). Los destinos posibles
    # son los nodos de INVESTIGATOR_NAMES (todos ya registrados).
    g.add_conditional_edges("plan", fan_out, list(INVESTIGATOR_NAMES))

    for agent_name in INVESTIGATOR_NAMES:
        g.add_edge(agent_name, "collect")

    g.add_edge("collect", "jueza")
    g.add_edge("jueza", "synthesize")
    g.add_edge("synthesize", "persist")
    g.add_edge("persist", END)

    return cast("Pregel[Any, Any, Any, Any]", g.compile(checkpointer=checkpointer))


__all__ = [
    "GraphDeps",
    "InvestigatorRunner",
    "build_graph",
]


# Type alias re-export por conveniencia
InvestigatorCallable = Callable[[dict[str, Any], dict[str, Any]], Awaitable[Any]]
