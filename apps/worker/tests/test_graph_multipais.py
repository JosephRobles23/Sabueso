"""Integration test del grafo en Modo Preview (S-18, country != 'pe').

Acceptance criteria del task:
- Investigation con ``country=cl`` completa usando 3 investigadores
  (buscador + letrado + periodista) — el subset reducido.
- Investigation con ``country=mx`` completa con datos placeholder.
- El estado final incluye un evento ``preview_mode_warning``.
- El dossier_md no queda vacío.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from src.llm.client import LLMClient, LLMResponse
from src.orchestrator import GraphDeps, build_graph, in_memory_checkpointer
from src.orchestrator.nodes.placeholders import InvestigatorRunner


class _StubLLM(LLMClient):
    def __init__(self, responses_by_model: dict[str, list[str]]) -> None:
        self._responses = {k: list(v) for k, v in responses_by_model.items()}
        self._calls: list[tuple[str, list[dict[str, Any]]]] = []
        from src.llm.routing import RouteResolver  # noqa: PLC0415

        self._resolver = RouteResolver()

    async def complete(  # type: ignore[override]
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        breakpoints: list[int] | None = None,
        state: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self._calls.append((model, messages))
        queue = self._responses.get(model)
        if not queue:
            raise AssertionError(f"_StubLLM: no response queued for model {model}")
        return LLMResponse(
            text=queue.pop(0),
            raw={},
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            model=model,
            provider="stub",
            cost_delta_usd=0.0,
            tool_calls=[],
        )


def _runner_for(callsign: str) -> InvestigatorRunner:
    async def runner(task: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        eid = state.get("target_entity_id") or str(uuid.uuid4())
        return {
            "claims": [
                {
                    "id": str(uuid.uuid4()),
                    "entity_id": eid,
                    "predicate": f"{callsign}_finding",
                    "object_value": {"summary": f"{callsign} encontró algo"},
                    "source_id": str(uuid.uuid4()),
                    "source_url": "https://example.org",
                    "confidence": 0.7,
                }
            ],
            "edges": [],
            "events": [],
        }

    return runner


@pytest.fixture
def plan_response_full_six() -> str:
    """El LLM devuelve los 6 investigadores; el plan node filtra a 3 en preview."""
    return (
        '{"plan": ['
        '{"agent": "buscador", "task": "Identificar entidad", "priority": 1},'
        '{"agent": "tasadora", "task": "Patrimonio", "priority": 2},'
        '{"agent": "contador", "task": "Contratos", "priority": 3},'
        '{"agent": "letrado", "task": "Normativa", "priority": 4},'
        '{"agent": "detective", "task": "Red familiar", "priority": 5},'
        '{"agent": "periodista", "task": "Prensa", "priority": 6}'
        "]}"
    )


@pytest.fixture
def dossier_md() -> str:
    return "# Dossier · Modo Preview\n\nResumen ejecutivo basado en 3 investigadores.\n"


@pytest.mark.asyncio
async def test_full_flow_country_cl_uses_three_investigators(
    plan_response_full_six: str,
    dossier_md: str,
) -> None:
    """Investigation con country=cl completa con buscador+letrado+periodista."""
    llm = _StubLLM(
        {
            "anthropic/claude-sonnet-4.6": [plan_response_full_six],
            "anthropic/claude-opus-4.7": [dossier_md],
        }
    )
    runners = {
        "buscador": _runner_for("buscador"),
        "letrado": _runner_for("letrado"),
        "periodista": _runner_for("periodista"),
        # Estos NO deberían ejecutarse en preview porque el plan los filtra:
        "tasadora": _runner_for("tasadora"),
        "contador": _runner_for("contador"),
        "detective": _runner_for("detective"),
    }
    deps = GraphDeps(
        llm=llm,
        investigator_runners=runners,
        persist_dry_run=True,
    )
    graph = build_graph(deps, checkpointer=in_memory_checkpointer())

    investigation_id = str(uuid.uuid4())
    final_state = await graph.ainvoke(
        {
            "investigation_id": investigation_id,
            "target_entity_id": str(uuid.uuid4()),
            "country": "cl",
            "locale": "es",
            "plan": [],
            "claims": [],
            "edges": [],
            "events": [],
        },
        config={"configurable": {"thread_id": f"cl-{investigation_id}"}},
    )

    # Plan filtrado al subset
    agents_in_plan = {s["agent"] for s in final_state["plan"]}
    assert agents_in_plan == {"buscador", "letrado", "periodista"}

    # Evento preview_mode_warning emitido
    warning = next(
        (e for e in final_state["events"] if e["type"] == "preview_mode_warning"),
        None,
    )
    assert warning is not None, "esperaba evento preview_mode_warning"
    assert warning["payload"]["country"] == "cl"
    assert warning["payload"]["available_investigators"] == [
        "el-buscador",
        "el-letrado",
        "el-periodista",
    ]
    assert warning["payload"]["reason"] == "limited_data_sources"

    # 3 claims (uno por investigador del subset), ninguno de Tasadora/Contador/Detective
    assert len(final_state["claims"]) == 3
    predicates = {c["predicate"] for c in final_state["claims"]}
    assert predicates == {
        "buscador_finding",
        "letrado_finding",
        "periodista_finding",
    }

    # Dossier no vacío
    assert final_state["dossier_md"]
    # Status final
    assert final_state["status"] == "complete"


@pytest.mark.asyncio
async def test_full_flow_country_mx_completes_with_placeholders(
    plan_response_full_six: str,
    dossier_md: str,
) -> None:
    """country=mx sin runners registrados: completa usando placeholders."""
    llm = _StubLLM(
        {
            "anthropic/claude-sonnet-4.6": [plan_response_full_six],
            "anthropic/claude-opus-4.7": [dossier_md],
        }
    )
    deps = GraphDeps(
        llm=llm,
        investigator_runners={},  # placeholders para todos
        persist_dry_run=True,
    )
    graph = build_graph(deps, checkpointer=in_memory_checkpointer())

    investigation_id = str(uuid.uuid4())
    final_state = await graph.ainvoke(
        {
            "investigation_id": investigation_id,
            "target_entity_id": str(uuid.uuid4()),
            "country": "mx",
            "locale": "es",
            "plan": [],
            "claims": [],
            "edges": [],
            "events": [],
        },
        config={"configurable": {"thread_id": f"mx-{investigation_id}"}},
    )

    # Plan filtrado al subset también para mx
    agents_in_plan = {s["agent"] for s in final_state["plan"]}
    assert agents_in_plan == {"buscador", "letrado", "periodista"}

    # Evento del modo preview con country=mx
    warning = next(
        e for e in final_state["events"] if e["type"] == "preview_mode_warning"
    )
    assert warning["payload"]["country"] == "mx"

    # Sin runners, los placeholders emiten agent_started/agent_finished
    # con claims_created=0, pero la investigación completa igual.
    event_types = {e["type"] for e in final_state["events"]}
    assert "agent_started" in event_types
    assert "agent_finished" in event_types
    assert "investigation_complete" in event_types
    assert final_state["status"] == "complete"
    assert final_state["dossier_md"]
