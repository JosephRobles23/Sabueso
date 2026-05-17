"""Integration test del grafo LangGraph de S-06.

Acceptance criteria (de docs/linear-tasks.md):

1. ``build_graph().compile()`` no falla.
2. Test integración: graph con 1 subagente mockeado completa todo el flujo.
3. State final tiene: ≥2 claims (del mock), status update, eventos
   emitidos, dossier_md no vacío.
4. Checkpoint queries: ``checkpointer.list({"configurable":
   {"thread_id": ...}})`` retorna ≥3 entradas (uno por step).
5. Sabueso plan retorna list[{agent, task, priority}] válido (verificado
   en evento ``plan_generated``).
6. fan_out emite tantos Send() como tasks en el plan.

Se usa InMemorySaver para no requerir Postgres en CI; la API
``list(config)`` es idéntica al PostgresSaver, así que la aserción de
"≥3 rows en checkpoints" se cumple con la misma semántica.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from src.llm.client import LLMClient, LLMResponse
from src.orchestrator import (
    DEFAULT_PLAN,
    GraphDeps,
    build_graph,
    fan_out,
    in_memory_checkpointer,
)
from src.orchestrator.nodes.placeholders import InvestigatorRunner


# ---------------------------------------------------------------- LLM stub
class _StubLLM(LLMClient):
    """LLMClient que devuelve respuestas predeterminadas por modelo.

    Hereda de LLMClient (no Mock) para mantener type-compatibility con
    los nodos que esperan ``LLMClient``. Sólo override ``complete``.
    """

    def __init__(self, responses_by_model: dict[str, list[str]]) -> None:
        # Skip super().__init__ — no necesitamos los transports reales.
        self._responses = {k: list(v) for k, v in responses_by_model.items()}
        self._calls: list[tuple[str, list[dict[str, Any]]]] = []
        # Resolver dummy (la fingerprint de LLMClient lo espera para .observe)
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
        text = queue.pop(0)
        return LLMResponse(
            text=text,
            raw={},
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            model=model,
            provider="stub",
            cost_delta_usd=0.0,
            tool_calls=[],
        )


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def investigation_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def target_entity_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def plan_response_json() -> str:
    # Sólo "contador" — el resto de los investigators corren como placeholders.
    return (
        '{"plan": [{"agent": "contador", '
        '"task": "Rastrear contratos públicos de la entidad", "priority": 1}]}'
    )


@pytest.fixture
def dossier_response_md() -> str:
    return (
        "# Dossier · Entidad Mock\n\n"
        "## Resumen ejecutivo\n"
        "- Se encontraron 2 claims relevantes.\n"
        "## Hallazgos por dimensión\n"
        "### Contratos públicos\n"
        "- Claim A — confidence 0.9\n"
    )


@pytest.fixture
def contador_runner(target_entity_id: str) -> InvestigatorRunner:
    """Mock de El Contador: emite 2 claims y 1 edge."""

    async def runner(task: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0)  # ceder loop para evidenciar concurrencia
        eid = state.get("target_entity_id") or target_entity_id
        source_id = str(uuid.uuid4())
        claim1 = {
            "id": str(uuid.uuid4()),
            "entity_id": eid,
            "predicate": "won_contract",
            "object_value": {"amount_pen": 1_500_000, "year": 2024},
            "source_id": source_id,
            "source_url": "https://seace.gob.pe/c1",
            "confidence": 0.9,
        }
        claim2 = {
            "id": str(uuid.uuid4()),
            "entity_id": eid,
            "predicate": "supplier_relationship",
            "object_value": {"counterparty": "Constructora XYZ"},
            "source_id": source_id,
            "source_url": "https://seace.gob.pe/c2",
            "confidence": 0.75,
        }
        edge = {
            "id": str(uuid.uuid4()),
            "from_entity": eid,
            "to_entity": str(uuid.uuid4()),
            "type": "contracted_with",
            "weight": 1.5,
            "confidence": 0.85,
        }
        return {
            "claims": [claim1, claim2],
            "edges": [edge],
            "events": [
                {
                    "type": "tool_call",
                    "agent": "el-contador",
                    "payload": {"tool": "seace_search", "args": {"ruc": "20100"}},
                }
            ],
        }

    return runner


# ---------------------------------------------------------------- tests
@pytest.mark.asyncio
async def test_build_graph_compiles_without_errors() -> None:
    """AC: ``build_graph().compile()`` no falla."""
    llm = _StubLLM({})
    graph = build_graph(GraphDeps(llm=llm, persist_dry_run=True))
    assert graph is not None


@pytest.mark.asyncio
async def test_fan_out_emits_one_send_per_plan_step() -> None:
    """AC: fan_out emite tantos Send() como tasks en el plan."""
    state = {
        "investigation_id": "x",
        "plan": [
            {"agent": "contador", "task": "A", "priority": 1},
            {"agent": "tasadora", "task": "B", "priority": 2},
            {"agent": "buscador", "task": "C", "priority": 3},
        ],
    }
    sends = fan_out(state)  # type: ignore[arg-type]
    assert len(sends) == 3
    assert {s.node for s in sends} == {"contador", "tasadora", "buscador"}


@pytest.mark.asyncio
async def test_fan_out_drops_unknown_agents() -> None:
    state = {
        "investigation_id": "x",
        "plan": [
            {"agent": "contador", "task": "A", "priority": 1},
            {"agent": "wizard", "task": "X", "priority": 2},
        ],
    }
    sends = fan_out(state)  # type: ignore[arg-type]
    assert {s.node for s in sends} == {"contador"}


@pytest.mark.asyncio
async def test_full_flow_with_one_mocked_subagent(
    investigation_id: str,
    target_entity_id: str,
    plan_response_json: str,
    dossier_response_md: str,
    contador_runner: InvestigatorRunner,
) -> None:
    """AC principal:
    - 1 subagente mockeado completa todo el flujo.
    - ≥2 claims.
    - status update visible.
    - eventos emitidos.
    - dossier_md no vacío.
    - ≥3 checkpoints por thread_id.
    """
    llm = _StubLLM(
        {
            "anthropic/claude-sonnet-4.6": [plan_response_json],
            "anthropic/claude-opus-4.7": [dossier_response_md],
        }
    )
    deps = GraphDeps(
        llm=llm,
        db_pool=None,
        investigator_runners={"contador": contador_runner},
        persist_dry_run=True,
    )
    checkpointer = in_memory_checkpointer()
    graph = build_graph(deps, checkpointer=checkpointer)

    thread_id = f"test-{investigation_id}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "investigation_id": investigation_id,
        "target_entity_id": target_entity_id,
        "country": "pe",
        "locale": "es",
        "user_query": "Investigar contratos",
        "plan": [],
        "claims": [],
        "edges": [],
        "events": [],
        "verified_claims": [],
        "dossier_md": "",
        "token_usage": {},
        "cost_usd": 0.0,
        "status": "pending",
    }

    final_state = await graph.ainvoke(initial_state, config=config)

    # ≥2 claims del mock
    assert len(final_state["claims"]) >= 2

    # status update completo
    assert final_state["status"] == "complete"

    # eventos: investigation_started + plan_generated + agent_started +
    # agent_finished + verification_done + synthesis_started +
    # investigation_complete (al menos)
    event_types = {e.get("type") for e in final_state["events"]}
    assert "investigation_started" in event_types
    assert "plan_generated" in event_types
    assert "agent_started" in event_types
    assert "agent_finished" in event_types
    assert "verification_done" in event_types
    assert "investigation_complete" in event_types

    # dossier no vacío + contiene secciones esperadas
    dossier = final_state["dossier_md"]
    assert dossier
    assert "# Dossier" in dossier

    # plan tiene shape válido
    plan = final_state["plan"]
    assert isinstance(plan, list) and len(plan) >= 1
    for step in plan:
        assert "agent" in step
        assert "task" in step
        assert "priority" in step

    # ≥3 checkpoints por thread_id (un row por step del grafo)
    checkpoints = list(checkpointer.list(config))
    assert len(checkpoints) >= 3, (
        f"esperaba ≥3 checkpoints, vi {len(checkpoints)}"
    )

    # plan_generated event tiene fallback=False (mock devolvió JSON válido)
    plan_event = next(e for e in final_state["events"] if e.get("type") == "plan_generated")
    assert plan_event["payload"]["fallback"] is False


@pytest.mark.asyncio
async def test_plan_node_falls_back_after_two_parse_failures(
    investigation_id: str,
    target_entity_id: str,
    dossier_response_md: str,
) -> None:
    """AC: Sabueso plan retry 1 vez si JSON malformado; si falla 2x,
    fallback a plan default."""
    llm = _StubLLM(
        {
            "anthropic/claude-sonnet-4.6": [
                "not json at all",
                "still not json },{",
            ],
            "anthropic/claude-opus-4.7": [dossier_response_md],
        }
    )
    deps = GraphDeps(
        llm=llm,
        investigator_runners={},  # ningún runner: todos placeholder
        persist_dry_run=True,
    )
    graph = build_graph(deps)
    thread_id = f"fallback-{investigation_id}"
    state = await graph.ainvoke(
        {
            "investigation_id": investigation_id,
            "target_entity_id": target_entity_id,
            "country": "pe",
            "locale": "es",
            "plan": [],
            "claims": [],
            "edges": [],
            "events": [],
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    assert state["plan"] == list(DEFAULT_PLAN)
    plan_event = next(e for e in state["events"] if e.get("type") == "plan_generated")
    assert plan_event["payload"]["fallback"] is True
    # Sonnet fue llamado dos veces (initial + 1 retry)
    sonnet_calls = [m for m, _ in llm._calls if m == "anthropic/claude-sonnet-4.6"]
    assert len(sonnet_calls) == 2


@pytest.mark.asyncio
async def test_persist_runs_transactional_when_pool_provided(
    investigation_id: str,
    target_entity_id: str,
    plan_response_json: str,
    dossier_response_md: str,
    contador_runner: InvestigatorRunner,
) -> None:
    """AC: persist ejecuta transacción atómica (rollback si algo falla).

    Verificamos que con un pool mock, el flujo abre transaction(), emite
    INSERTs, y commitea. El rollback (transaction __aexit__ con excepción)
    se testea en test_persist_rollback_on_failure.
    """
    calls: list[tuple[str, tuple[Any, ...]]] = []

    class FakeTxn:
        async def __aenter__(self) -> FakeTxn:
            calls.append(("BEGIN", ()))
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            calls.append(("COMMIT" if exc is None else "ROLLBACK", ()))
            return False

    class FakeConn:
        def transaction(self) -> FakeTxn:
            return FakeTxn()

        async def execute(self, query: str, *args: Any) -> str:
            head = query.strip().split()[0]
            calls.append((head, args))
            return f"{head} 1"

    class FakeAcquireCM:
        async def __aenter__(self) -> FakeConn:
            return FakeConn()

        async def __aexit__(self, *_a: Any) -> bool:
            return False

    class FakePool:
        def acquire(self) -> FakeAcquireCM:
            return FakeAcquireCM()

    llm = _StubLLM(
        {
            "anthropic/claude-sonnet-4.6": [plan_response_json],
            "anthropic/claude-opus-4.7": [dossier_response_md],
        }
    )
    deps = GraphDeps(
        llm=llm,
        db_pool=FakePool(),
        investigator_runners={"contador": contador_runner},
        persist_dry_run=False,
    )
    graph = build_graph(deps)

    state = await graph.ainvoke(
        {
            "investigation_id": investigation_id,
            "target_entity_id": target_entity_id,
            "country": "pe",
            "locale": "es",
            "plan": [],
            "claims": [],
            "edges": [],
            "events": [],
        },
        config={"configurable": {"thread_id": f"tx-{investigation_id}"}},
    )

    op_sequence = [c[0] for c in calls]
    assert "BEGIN" in op_sequence
    assert "COMMIT" in op_sequence
    assert "ROLLBACK" not in op_sequence
    # Una UPDATE a investigations + 2 INSERTs a claims + 1 INSERT a edges
    assert op_sequence.count("UPDATE") == 1
    assert op_sequence.count("INSERT") >= 3
    assert state["status"] == "complete"


@pytest.mark.asyncio
async def test_persist_rollback_on_failure(
    investigation_id: str,
    target_entity_id: str,
    plan_response_json: str,
    dossier_response_md: str,
    contador_runner: InvestigatorRunner,
) -> None:
    """AC: persist hace rollback si algo falla dentro de la transacción."""
    calls: list[str] = []

    class FailingTxn:
        async def __aenter__(self) -> FailingTxn:
            calls.append("BEGIN")
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            calls.append("COMMIT" if exc is None else "ROLLBACK")
            return False

    class FailingConn:
        def __init__(self) -> None:
            self._n = 0

        def transaction(self) -> FailingTxn:
            return FailingTxn()

        async def execute(self, query: str, *args: Any) -> str:
            self._n += 1
            if self._n == 2:  # explota en el primer INSERT
                raise RuntimeError("simulated DB error")
            return "ok"

    class CM:
        async def __aenter__(self) -> FailingConn:
            return FailingConn()

        async def __aexit__(self, *_a: Any) -> bool:
            return False

    class FailingPool:
        def acquire(self) -> CM:
            return CM()

    llm = _StubLLM(
        {
            "anthropic/claude-sonnet-4.6": [plan_response_json],
            "anthropic/claude-opus-4.7": [dossier_response_md],
        }
    )
    deps = GraphDeps(
        llm=llm,
        db_pool=FailingPool(),
        investigator_runners={"contador": contador_runner},
        persist_dry_run=False,
    )
    graph = build_graph(deps)

    state = await graph.ainvoke(
        {
            "investigation_id": investigation_id,
            "target_entity_id": target_entity_id,
            "country": "pe",
            "locale": "es",
            "plan": [],
            "claims": [],
            "edges": [],
            "events": [],
        },
        config={"configurable": {"thread_id": f"rb-{investigation_id}"}},
    )

    assert "BEGIN" in calls
    assert "ROLLBACK" in calls
    assert "COMMIT" not in calls
    assert state["status"] == "failed"
    failed_events = [e for e in state["events"] if e.get("type") == "investigation_failed"]
    assert failed_events, "esperaba investigation_failed evento tras rollback"
