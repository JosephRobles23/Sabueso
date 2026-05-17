"""E2E integration test del milestone S-10.

Verifica el flujo completo con El Contador real (no placeholder) y un único
investigador activo:

    plan → fan_out → contador → collect → jueza_placeholder → synthesize → persist

Mocks:
- LLM: ``_StubLLM`` que devuelve respuestas predeterminadas por modelo
  (sonnet para plan, kimi para el plan de El Contador, opus para dossier).
- Tool ``search_seace_contracts``: registramos un handler fake en el
  ToolRegistry que devuelve un ``SeaceOutput`` con 2 contratos.

Acceptance:
- final_state.status == "complete"
- ≥1 claim emitido por El Contador
- dossier_md no vacío
- cost_usd < $0.50

El test usa ``persist_dry_run=True`` y ``in_memory_checkpointer()`` para no
requerir Postgres.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from src.investigators.contador import ElContador
from src.llm.client import LLMClient, LLMResponse
from src.llm.routing import RouteResolver
from src.orchestrator import GraphDeps, build_graph, in_memory_checkpointer
from src.tools.pe._common import Money, Source
from src.tools.pe.seace import SeaceContract, SeaceOutput
from src.tools.registry import ToolDef, ToolRegistry


# ----------------------------------------------------------------- LLM stub
class _StubLLM(LLMClient):
    """LLMClient que devuelve respuestas predeterminadas por modelo y
    contabiliza cost_usd fake. Hereda de LLMClient para satisfacer el type
    de GraphDeps + BaseInvestigator."""

    def __init__(self, responses_by_model: dict[str, list[str]]) -> None:
        self._responses = {k: list(v) for k, v in responses_by_model.items()}
        self.calls: list[tuple[str, list[dict[str, Any]]]] = []
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
        self.calls.append((model, messages))
        queue = self._responses.get(model)
        if not queue:
            raise AssertionError(f"_StubLLM: no response queued for model {model}")
        text = queue.pop(0)
        # Inflar cost_usd un poquito para validar el budget cap < $0.50
        if state is not None:
            state["cost_usd"] = float(state.get("cost_usd") or 0.0) + 0.05
        return LLMResponse(
            text=text,
            raw={},
            usage={"prompt_tokens": 200, "completion_tokens": 80},
            model=model,
            provider="stub",
            cost_delta_usd=0.05,
        )


# ----------------------------------------------------------------- fixtures
@pytest.fixture
def isolated_seace_tool():
    """Registra un fake `search_seace_contracts` para Perú durante el test."""
    snapshot = dict(ToolRegistry._tools)
    ToolRegistry._tools.clear()

    async def fake_search(payload: Any) -> SeaceOutput:
        ruc = payload.ruc if hasattr(payload, "ruc") else payload.get("ruc")
        return SeaceOutput(
            ruc=ruc,
            contracts=[
                SeaceContract(
                    ocid="ocds-pe-001",
                    title="Adquisición de medicamentos oncológicos",
                    buyer="Ministerio de Salud",
                    supplier="Farmaceutica DemoPe SAC",
                    award_date="2024-03-15",
                    value=Money(amount=1_500_000.50, currency="PEN"),
                    url="https://contratacionesabiertas.osce.gob.pe/r/ocds-pe-001",
                ),
                SeaceContract(
                    ocid="ocds-pe-002",
                    title="Servicio de mantenimiento hospitalario",
                    buyer="Ministerio de Salud",
                    supplier="Servicios DemoPe EIRL",
                    award_date="2023-09-01",
                    value=Money(amount=320_000.0, currency="PEN"),
                    url="https://contratacionesabiertas.osce.gob.pe/r/ocds-pe-002",
                ),
            ],
            total_amount=Money(amount=1_820_000.50, currency="PEN"),
            pages_fetched=1,
            sources=[
                Source(
                    url=f"https://contratacionesabiertas.osce.gob.pe/buscador-de-contrataciones?ruc={ruc}",
                    source_type="seace",
                    title=f"SEACE — contrataciones RUC {ruc}",
                )
            ],
        )

    from src.tools.pe.seace import SeaceInput
    from src.tools.pe.seace import SeaceOutput as _Out

    ToolRegistry.register_tool(
        ToolDef(
            name="search_seace_contracts",
            country="pe",
            handler=fake_search,
            description="Fake SEACE handler for tests",
            input_model=SeaceInput,
            output_model=_Out,
            cache_ttl=0,
            tags=("contracts",),
        )
    )

    yield
    ToolRegistry._tools.clear()
    ToolRegistry._tools.update(snapshot)


@pytest.fixture
def investigation_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def target_entity_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def plan_response_json() -> str:
    # Sabueso dirige toda la investigación a "contador".
    return json.dumps(
        {
            "plan": [
                {
                    "agent": "contador",
                    "task": "Rastrear contratos del MINSA (RUC 20131373237)",
                    "priority": 1,
                }
            ]
        }
    )


@pytest.fixture
def contador_plan_json() -> str:
    # El plan ReWOO de El Contador: 1 step a search_seace_contracts.
    return json.dumps(
        {
            "steps": [
                {
                    "tool": "search_seace_contracts",
                    "args": {"ruc": "20131373237", "year_from": 2020, "year_to": 2024},
                }
            ]
        }
    )


@pytest.fixture
def dossier_md() -> str:
    return (
        "# Dossier · MINSA\n\n"
        "## Resumen ejecutivo\n"
        "- 2 contratos identificados, S/ 1.82M en total.\n"
        "## Contratos públicos\n"
        "- Adquisición de medicamentos oncológicos — S/ 1.5M (2024).\n"
    )


# ------------------------------------------------------------------- tests
@pytest.mark.asyncio
async def test_e2e_contador_emits_claims_and_completes(
    isolated_seace_tool: None,
    investigation_id: str,
    target_entity_id: str,
    plan_response_json: str,
    contador_plan_json: str,
    dossier_md: str,
) -> None:
    """Flujo principal del milestone S-10."""
    llm = _StubLLM(
        {
            # Sabueso plan
            "anthropic/claude-sonnet-4.6": [plan_response_json],
            # El Contador (ReWOO plan)
            "moonshot/kimi-k2.6": [contador_plan_json],
            # Sabueso synthesize
            "anthropic/claude-opus-4.7": [dossier_md],
        }
    )

    contador = ElContador(country="pe", locale="es", llm=llm)
    deps = GraphDeps(
        llm=llm,
        db_pool=None,
        investigator_runners={"contador": contador.run},
        persist_dry_run=True,
    )

    checkpointer = in_memory_checkpointer()
    graph = build_graph(deps, checkpointer=checkpointer)

    initial_state: dict[str, Any] = {
        "investigation_id": investigation_id,
        "target_entity_id": target_entity_id,
        "country": "pe",
        "locale": "es",
        "user_query": "Investigar contratos del MINSA",
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

    final_state = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": f"e2e-{investigation_id}"}},
    )

    # status terminal
    assert final_state["status"] == "complete", final_state.get("status")

    # ≥1 claim emitido por El Contador (2 awarded_contract + 1 summary = 3)
    claims = final_state["claims"]
    assert len(claims) >= 1, f"se esperaban claims de El Contador, llegaron {len(claims)}"

    predicates = {c.get("predicate") for c in claims}
    assert "awarded_contract" in predicates, predicates
    assert "total_contracts_awarded" in predicates, predicates

    # claims llevan el agent_callsign de El Contador
    callsigns = {c.get("agent_callsign") for c in claims}
    assert callsigns == {"el-contador"}, callsigns

    # dossier_md no vacío
    dossier = final_state["dossier_md"]
    assert dossier and dossier.strip(), "dossier_md vacío"

    # cost_usd dentro del budget cap del E2E (<$0.50)
    cost = float(final_state.get("cost_usd") or 0.0)
    assert cost < 0.50, f"cost_usd={cost} excede $0.50"

    # eventos esperados del flujo completo
    event_types = {e.get("type") for e in final_state["events"]}
    assert "investigation_started" in event_types
    assert "plan_generated" in event_types
    assert "agent_started" in event_types
    assert "agent_finished" in event_types
    assert "verification_done" in event_types
    assert "investigation_complete" in event_types


@pytest.mark.asyncio
async def test_e2e_contador_high_value_flagged(
    isolated_seace_tool: None,
    investigation_id: str,
    target_entity_id: str,
    plan_response_json: str,
    contador_plan_json: str,
    dossier_md: str,
) -> None:
    """Cada contrato > S/ 1M lleva ``notes.high_value=true`` en object_value."""
    llm = _StubLLM(
        {
            "anthropic/claude-sonnet-4.6": [plan_response_json],
            "moonshot/kimi-k2.6": [contador_plan_json],
            "anthropic/claude-opus-4.7": [dossier_md],
        }
    )
    contador = ElContador(country="pe", locale="es", llm=llm)
    deps = GraphDeps(
        llm=llm,
        investigator_runners={"contador": contador.run},
        persist_dry_run=True,
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
        config={"configurable": {"thread_id": f"hv-{investigation_id}"}},
    )

    high_value = [
        c
        for c in state["claims"]
        if c.get("predicate") == "awarded_contract"
        and (c.get("object_value") or {}).get("notes", {}).get("high_value")
    ]
    assert len(high_value) == 1
    assert high_value[0]["object_value"]["amount"] == 1_500_000.50


@pytest.mark.asyncio
async def test_e2e_contador_tool_permission_gate(
    isolated_seace_tool: None,
    investigation_id: str,
    target_entity_id: str,
    plan_response_json: str,
    dossier_md: str,
) -> None:
    """Si el plan del Contador pide una tool no permitida, el step retorna un
    error y se materializa como claim ``investigation_error``."""
    forbidden_plan = json.dumps(
        {
            "steps": [
                {"tool": "search_sunarp_records", "args": {"dni": "12345678"}},
            ]
        }
    )
    llm = _StubLLM(
        {
            "anthropic/claude-sonnet-4.6": [plan_response_json],
            "moonshot/kimi-k2.6": [forbidden_plan],
            "anthropic/claude-opus-4.7": [dossier_md],
        }
    )
    contador = ElContador(country="pe", locale="es", llm=llm)
    deps = GraphDeps(
        llm=llm,
        investigator_runners={"contador": contador.run},
        persist_dry_run=True,
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
        config={"configurable": {"thread_id": f"perm-{investigation_id}"}},
    )

    error_claims = [
        c for c in state["claims"] if c.get("predicate") == "investigation_error"
    ]
    assert len(error_claims) == 1
    assert "search_sunarp_records" in error_claims[0]["object_value"]["error"]
    # El flujo siguió hasta complete (los errores se capturan, no estallan).
    assert state["status"] == "complete"
