"""Tests del InvestigationState — semántica de merge concurrente.

LangGraph mergea las actualizaciones de canales que tienen un reducer
``Annotated[list, operator.add]`` concatenando. Cuando varios Send()
emitidos por ``fan_out`` corren en paralelo, cada uno aporta su delta y
la reducción debe respetar la unión completa (no perder claims de una
rama que terminó antes que otra, ni reemplazar la lista entera).

Tests:
1. El TypedDict tiene ``add`` como reducer en claims/edges/events.
2. Merge funcional con operator.add preserva todos los items.
3. Test integración con LangGraph corriendo dos branches en paralelo,
   cada una appendea su propio claim.
"""

from __future__ import annotations

from operator import add
from typing import Any, get_type_hints

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.orchestrator.checkpointer import in_memory_checkpointer
from src.orchestrator.state import InvestigationState


def test_claims_field_uses_add_reducer() -> None:
    hints = get_type_hints(InvestigationState, include_extras=True)
    for field in ("claims", "edges", "events"):
        ann = hints[field]
        metadata = getattr(ann, "__metadata__", ())
        assert add in metadata, f"{field} should be Annotated[..., add]"


def test_functional_merge_with_add_preserves_all_items() -> None:
    initial: list[dict[str, Any]] = [{"id": "a"}]
    branch1 = [{"id": "b"}, {"id": "c"}]
    branch2 = [{"id": "d"}]
    merged = add(add(initial, branch1), branch2)
    assert [c["id"] for c in merged] == ["a", "b", "c", "d"]


@pytest.mark.asyncio
async def test_langgraph_merges_parallel_branches_via_reducer() -> None:
    """Integración: 2 ramas paralelas appendean al canal ``claims`` y
    LangGraph aplica el reducer add para que ambos claims sobrevivan."""

    async def kickoff(state: InvestigationState) -> dict[str, Any]:
        return {"plan": [{"agent": "n1", "task": "x"}, {"agent": "n2", "task": "y"}]}

    def route(state: InvestigationState) -> list[Send]:
        return [
            Send("n1", {**state, "current_task": {"agent": "n1"}}),
            Send("n2", {**state, "current_task": {"agent": "n2"}}),
        ]

    async def branch1(state: InvestigationState) -> dict[str, Any]:
        return {"claims": [{"id": "from-1"}]}

    async def branch2(state: InvestigationState) -> dict[str, Any]:
        return {"claims": [{"id": "from-2"}]}

    async def end_node(state: InvestigationState) -> dict[str, Any]:
        return {}

    g: StateGraph = StateGraph(InvestigationState)
    g.add_node("kickoff", kickoff)
    g.add_node("n1", branch1)
    g.add_node("n2", branch2)
    g.add_node("end_node", end_node)
    g.add_edge(START, "kickoff")
    g.add_conditional_edges("kickoff", route, ["n1", "n2"])
    g.add_edge("n1", "end_node")
    g.add_edge("n2", "end_node")
    g.add_edge("end_node", END)

    app = g.compile(checkpointer=in_memory_checkpointer())
    initial: dict[str, Any] = {
        "investigation_id": "test",
        "claims": [{"id": "initial"}],
        "edges": [],
        "events": [],
        "plan": [],
    }
    result = await app.ainvoke(
        initial, config={"configurable": {"thread_id": "merge-test"}}
    )

    ids = [c["id"] for c in result["claims"]]
    assert "initial" in ids
    assert "from-1" in ids
    assert "from-2" in ids
    assert len(ids) == 3
