"""Tests del branching multi-país en el plan node de Sabueso (S-18).

Acceptance criteria del task:
- ``state.country != "pe"`` → plan filtrado a buscador + letrado + periodista.
- ``preview_mode_warning`` event con ``{country, available_investigators,
  available_sources, reason}`` y callsigns "el-*" como el resto del SSE.
- Para ``country == "pe"`` el plan completo (6 investigadores) queda intacto
  y NO se emite preview_mode_warning.
- El user message del LLM lleva la restricción dura (catálogo limitado +
  lista negra de Tasadora/Contador/Detective).
- El system message renderizado incluye ``limited_list`` y la nota de Modo
  Preview cuando ``country != "pe"``.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from src.llm.client import LLMClient, LLMResponse
from src.orchestrator.nodes.plan import (
    PREVIEW_INVESTIGATORS,
    PlanDeps,
    _filter_for_preview,
    _is_preview,
    _source_summary,
    make_plan_node,
)
from src.prompts.loader import PromptLoader


class _StubLLM(LLMClient):
    """LLMClient que captura mensajes y devuelve un plan fijo por modelo."""

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
            raise AssertionError(f"_StubLLM: no response queued for {model}")
        return LLMResponse(
            text=queue.pop(0),
            raw={},
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            model=model,
            provider="stub",
            cost_delta_usd=0.0,
            tool_calls=[],
        )


# ---------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------
def test_is_preview_true_for_non_pe():
    assert _is_preview("cl") is True
    assert _is_preview("mx") is True
    assert _is_preview("sv") is True


def test_is_preview_false_for_pe_and_none():
    assert _is_preview("pe") is False
    assert _is_preview(None) is False


def test_source_summary_known_country_returns_specific_catalog():
    assert "BCN" in _source_summary("cl")
    assert "Asamblea" in _source_summary("sv")


def test_source_summary_unknown_country_falls_back_to_pe():
    assert _source_summary("ar") == _source_summary("pe")


def test_filter_for_preview_drops_non_subset_investigators():
    plan: list[Any] = [
        {"agent": "contador", "task": "x", "priority": 1},
        {"agent": "tasadora", "task": "y", "priority": 2},
        {"agent": "letrado", "task": "z", "priority": 3},
    ]
    filtered = _filter_for_preview(plan)
    assert [s["agent"] for s in filtered] == ["letrado"]


def test_filter_for_preview_substitutes_when_subset_empty():
    plan: list[Any] = [
        {"agent": "contador", "task": "x", "priority": 1},
        {"agent": "tasadora", "task": "y", "priority": 2},
    ]
    filtered = _filter_for_preview(plan)
    agents = {s["agent"] for s in filtered}
    assert agents == set(PREVIEW_INVESTIGATORS)
    assert len(filtered) == 3


# ---------------------------------------------------------------------------
# Plan node end-to-end (sin grafo)
# ---------------------------------------------------------------------------
@pytest.fixture
def plan_with_all_six() -> str:
    return (
        '{"plan": ['
        '{"agent": "buscador", "task": "identificar", "priority": 1},'
        '{"agent": "tasadora", "task": "patrimonio", "priority": 2},'
        '{"agent": "contador", "task": "contratos", "priority": 3},'
        '{"agent": "letrado", "task": "leyes", "priority": 4},'
        '{"agent": "detective", "task": "familia", "priority": 5},'
        '{"agent": "periodista", "task": "prensa", "priority": 6}'
        "]}"
    )


@pytest.mark.asyncio
async def test_plan_pe_keeps_all_six_investigators(plan_with_all_six: str):
    llm = _StubLLM({"anthropic/claude-sonnet-4.6": [plan_with_all_six]})
    node = make_plan_node(PlanDeps(llm=llm, prompt_loader=PromptLoader()))

    result = await node(
        {
            "investigation_id": str(uuid.uuid4()),
            "target_entity_id": str(uuid.uuid4()),
            "country": "pe",
            "locale": "es",
        }
    )

    agents = [s["agent"] for s in result["plan"]]
    assert set(agents) == {
        "buscador",
        "tasadora",
        "contador",
        "letrado",
        "detective",
        "periodista",
    }
    event_types = [e["type"] for e in result["events"]]
    assert "preview_mode_warning" not in event_types


@pytest.mark.asyncio
async def test_plan_cl_filters_to_preview_subset(plan_with_all_six: str):
    llm = _StubLLM({"anthropic/claude-sonnet-4.6": [plan_with_all_six]})
    node = make_plan_node(PlanDeps(llm=llm, prompt_loader=PromptLoader()))

    result = await node(
        {
            "investigation_id": str(uuid.uuid4()),
            "target_entity_id": str(uuid.uuid4()),
            "country": "cl",
            "locale": "es",
        }
    )

    agents = {s["agent"] for s in result["plan"]}
    assert agents == set(PREVIEW_INVESTIGATORS)

    warning = next(e for e in result["events"] if e["type"] == "preview_mode_warning")
    assert warning["payload"]["country"] == "cl"
    assert warning["payload"]["available_investigators"] == [
        "el-buscador",
        "el-letrado",
        "el-periodista",
    ]
    assert warning["payload"]["available_sources"]
    assert warning["payload"]["reason"] == "limited_data_sources"


@pytest.mark.asyncio
async def test_plan_mx_substitutes_when_llm_only_returns_non_preview():
    """Si el LLM (mal calibrado) sólo manda Tasadora a MX, sustituimos."""
    bad_plan = (
        '{"plan": ['
        '{"agent": "tasadora", "task": "patrimonio", "priority": 1},'
        '{"agent": "contador", "task": "contratos", "priority": 2}'
        "]}"
    )
    llm = _StubLLM({"anthropic/claude-sonnet-4.6": [bad_plan]})
    node = make_plan_node(PlanDeps(llm=llm, prompt_loader=PromptLoader()))

    result = await node(
        {
            "investigation_id": str(uuid.uuid4()),
            "target_entity_id": str(uuid.uuid4()),
            "country": "mx",
            "locale": "es",
        }
    )

    agents = {s["agent"] for s in result["plan"]}
    assert agents == set(PREVIEW_INVESTIGATORS)
    assert any(e["type"] == "preview_mode_warning" for e in result["events"])


@pytest.mark.asyncio
async def test_plan_renders_prompt_with_limited_list(plan_with_all_six: str):
    """El prompt debe mencionar el catálogo limitado del país en preview."""
    llm = _StubLLM({"anthropic/claude-sonnet-4.6": [plan_with_all_six]})
    node = make_plan_node(PlanDeps(llm=llm, prompt_loader=PromptLoader()))

    await node(
        {
            "investigation_id": str(uuid.uuid4()),
            "target_entity_id": str(uuid.uuid4()),
            "country": "cl",
            "locale": "es",
        }
    )

    # El system message es el primer mensaje del primer call. Concatenamos
    # los bloques text para inspeccionarlo.
    _model, messages = llm._calls[0]
    system_blocks = messages[0]["content"]
    rendered = " ".join(b["text"] for b in system_blocks)
    assert "Modo Preview" in rendered
    assert "BCN" in rendered  # parte de _source_summary("cl")
    assert "buscador, letrado, periodista" in rendered


@pytest.mark.asyncio
async def test_plan_user_message_carries_hard_constraint(plan_with_all_six: str):
    """En preview el user prompt debe incluir la restricción dura textual."""
    llm = _StubLLM({"anthropic/claude-sonnet-4.6": [plan_with_all_six]})
    node = make_plan_node(PlanDeps(llm=llm, prompt_loader=PromptLoader()))

    await node(
        {
            "investigation_id": str(uuid.uuid4()),
            "target_entity_id": str(uuid.uuid4()),
            "country": "mx",
            "locale": "es",
        }
    )

    _model, messages = llm._calls[0]
    user_msg = messages[1]["content"]
    assert "RESTRICCIÓN DURA" in user_msg
    assert "Plan reducido. Disponibles para mx" in user_msg
    assert "NO uses la-tasadora, el-contador ni el-detective" in user_msg


@pytest.mark.asyncio
async def test_plan_user_message_has_no_constraint_in_pe(plan_with_all_six: str):
    """En PE el user prompt NO debe inyectar la restricción dura."""
    llm = _StubLLM({"anthropic/claude-sonnet-4.6": [plan_with_all_six]})
    node = make_plan_node(PlanDeps(llm=llm, prompt_loader=PromptLoader()))

    await node(
        {
            "investigation_id": str(uuid.uuid4()),
            "target_entity_id": str(uuid.uuid4()),
            "country": "pe",
            "locale": "es",
        }
    )

    _model, messages = llm._calls[0]
    user_msg = messages[1]["content"]
    assert "RESTRICCIÓN DURA" not in user_msg


@pytest.mark.asyncio
async def test_preview_warning_payload_validates_against_schema(
    plan_with_all_six: str,
):
    """El payload del evento debe parsear contra PreviewModeWarningPayload."""
    from src.events.schemas import PreviewModeWarningPayload  # noqa: PLC0415

    llm = _StubLLM({"anthropic/claude-sonnet-4.6": [plan_with_all_six]})
    node = make_plan_node(PlanDeps(llm=llm, prompt_loader=PromptLoader()))

    result = await node(
        {
            "investigation_id": str(uuid.uuid4()),
            "target_entity_id": str(uuid.uuid4()),
            "country": "sv",
            "locale": "es",
        }
    )

    warning = next(e for e in result["events"] if e["type"] == "preview_mode_warning")
    payload = PreviewModeWarningPayload.model_validate(warning["payload"])
    assert payload.country == "sv"
    assert payload.reason == "limited_data_sources"
    assert payload.available_investigators == [
        "el-buscador",
        "el-letrado",
        "el-periodista",
    ]


@pytest.mark.asyncio
async def test_plan_cl_keeps_three_investigators_when_llm_returns_full_six(
    plan_with_all_six: str,
):
    """country=cl + plan completo del LLM → plan final tiene sólo 3 investigadores."""
    llm = _StubLLM({"anthropic/claude-sonnet-4.6": [plan_with_all_six]})
    node = make_plan_node(PlanDeps(llm=llm, prompt_loader=PromptLoader()))

    result = await node(
        {
            "investigation_id": str(uuid.uuid4()),
            "target_entity_id": str(uuid.uuid4()),
            "country": "cl",
            "locale": "es",
        }
    )

    assert len(result["plan"]) == 3
    agents = {s["agent"] for s in result["plan"]}
    assert agents == set(PREVIEW_INVESTIGATORS)
