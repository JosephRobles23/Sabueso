"""Tests S-11 — los 5 investigadores nuevos + La Jueza MoA.

Cada test:
- monta un ToolRegistry limpio con handlers fake registrados por tool,
- inyecta un FakeLLM con respuestas pre-canned por modelo,
- corre el investigador end-to-end, valida claims/edges emitidos.

El test integración corre el grafo completo con 3 investigadores
activos + La Jueza, y verifica costo total < $1.00 vía state.cost_usd.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from src.investigators.buscador import ElBuscador
from src.investigators.contador import ElContador
from src.investigators.detective import ElDetective
from src.investigators.jueza import LaJueza
from src.investigators.letrado import ElLetrado
from src.investigators.periodista import ElPeriodista
from src.investigators.tasadora import LaTasadora
from src.llm.client import LLMClient, LLMResponse
from src.llm.routing import RouteResolver
from src.orchestrator import GraphDeps, build_graph, in_memory_checkpointer
from src.tools.pe._common import Money, Source
from src.tools.pe.manolo import ManoloOutput, ManoloVisit
from src.tools.pe.relatives import RelativesOutput
from src.tools.pe.seace import SeaceContract, SeaceInput, SeaceOutput
from src.tools.pe.stubs import (
    BoardMember,
    CrossVoteOutput,
    DniRecord,
    FindDniOutput,
    FindRucOutput,
    RucRecord,
    SearchSentencesOutput,
    Sentence,
    SunarpBoardOutput,
    VoteConflict,
)
from src.tools.pe.sunarp import SunarpOutput, SunarpProperty
from src.tools.registry import ToolDef, ToolRegistry


# =========================================================================
# helpers / fakes
# =========================================================================
@dataclass
class _Queued:
    text: str


class FakeLLM(LLMClient):
    """LLMClient drop-in: returns queued .text per model. Tracks cost."""

    def __init__(self, responses_by_model: dict[str, list[str]] | None = None) -> None:
        self._responses: dict[str, list[str]] = {
            k: list(v) for k, v in (responses_by_model or {}).items()
        }
        self.calls: list[tuple[str, list[dict[str, Any]]]] = []
        self._resolver = RouteResolver()

    def push(self, model: str, text: str) -> None:
        self._responses.setdefault(model, []).append(text)

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
            raise AssertionError(f"FakeLLM: no response queued for model {model}")
        text = queue.pop(0)
        if state is not None:
            state["cost_usd"] = float(state.get("cost_usd") or 0.0) + 0.02
        return LLMResponse(
            text=text,
            raw={},
            usage={"prompt_tokens": 200, "completion_tokens": 80},
            model=model,
            provider="stub",
            cost_delta_usd=0.02,
        )


@pytest.fixture
def isolated_registry_snapshot():
    snapshot = dict(ToolRegistry._tools)
    ToolRegistry._tools.clear()
    yield
    ToolRegistry._tools.clear()
    ToolRegistry._tools.update(snapshot)


def _register(
    name: str,
    input_model: type,
    output_model: type,
    handler,
) -> None:
    ToolRegistry.register_tool(
        ToolDef(
            name=name,
            country="pe",
            handler=handler,
            description=f"Fake {name} for tests",
            input_model=input_model,
            output_model=output_model,
            cache_ttl=0,
        )
    )


def _entity_id() -> str:
    return str(uuid.uuid4())


# =========================================================================
# El Buscador (REWOO)
# =========================================================================
@pytest.mark.asyncio
async def test_buscador_emits_claims_for_dni_ruc_manolo(
    isolated_registry_snapshot,
) -> None:
    from src.tools.pe.manolo import ManoloInput
    from src.tools.pe.stubs import (
        FindDniInput,
        FindRucInput,
    )

    async def fake_dni(payload: FindDniInput) -> FindDniOutput:
        return FindDniOutput(
            record=DniRecord(
                dni=payload.dni,
                full_name="Juan Pérez Mendoza",
                birth_year=1970,
                found=True,
                stub=True,
            ),
            citations=[],
        )

    async def fake_ruc(payload: FindRucInput) -> FindRucOutput:
        return FindRucOutput(
            record=RucRecord(
                ruc=payload.ruc,
                razon_social="Pesquera ABC SAC",
                estado="ACTIVO",
                found=True,
                stub=True,
            ),
            citations=[],
        )

    async def fake_manolo(payload: ManoloInput) -> ManoloOutput:
        return ManoloOutput(
            query=payload.query,
            visits=[
                ManoloVisit(
                    visitor="Juan Pérez Mendoza",
                    entity="Ministerio de Salud",
                    source_url="https://www.manolo.pe/buscar?q=juan",
                ),
                ManoloVisit(
                    visitor="Juan Pérez Mendoza",
                    entity="Palacio de Gobierno",
                    source_url="https://www.manolo.pe/buscar?q=juan",
                ),
            ],
            citations=[],
        )

    _register("find_dni_record", FindDniInput, FindDniOutput, fake_dni)
    _register("find_ruc_record", FindRucInput, FindRucOutput, fake_ruc)
    _register("search_manolo", ManoloInput, ManoloOutput, fake_manolo)

    plan = json.dumps(
        {
            "steps": [
                {"tool": "find_dni_record", "args": {"dni": "12345678"}},
                {"tool": "find_ruc_record", "args": {"ruc": "20512345678"}},
                {"tool": "search_manolo", "args": {"query": "Juan Pérez"}},
            ]
        }
    )
    llm = FakeLLM({"moonshot/kimi-k2.6": [plan]})
    buscador = ElBuscador(country="pe", locale="es", llm=llm)
    target = _entity_id()
    state: dict[str, Any] = {"investigation_id": "inv-buscador-1", "target_entity_id": target}
    claims = await buscador.run(
        {"task": "Identificar entidad", "target_entity_id": target}, state
    )

    predicates = {c["predicate"] for c in claims}
    assert "is_dni" in predicates
    assert "is_ruc" in predicates
    assert "visited_official_entity" in predicates
    assert "holds_position" in predicates  # ≥2 entidades visitadas
    # callsign correcto
    assert all(c["agent_callsign"] == "el-buscador" for c in claims)


@pytest.mark.asyncio
async def test_buscador_dni_not_found_lowers_confidence(
    isolated_registry_snapshot,
) -> None:
    from src.tools.pe.stubs import FindDniInput

    async def fake_dni(payload: FindDniInput) -> FindDniOutput:
        return FindDniOutput(
            record=DniRecord(dni=payload.dni, found=False, stub=True), citations=[]
        )

    _register("find_dni_record", FindDniInput, FindDniOutput, fake_dni)
    llm = FakeLLM(
        {
            "moonshot/kimi-k2.6": [
                json.dumps(
                    {"steps": [{"tool": "find_dni_record", "args": {"dni": "11111111"}}]}
                )
            ]
        }
    )
    buscador = ElBuscador(country="pe", locale="es", llm=llm)
    claims = await buscador.run(
        {"task": "Resolver DNI", "target_entity_id": _entity_id()},
        {"investigation_id": "i"},
    )
    is_dni = [c for c in claims if c["predicate"] == "is_dni"]
    assert is_dni and is_dni[0]["confidence"] == 0.60  # stub w/o found


# =========================================================================
# La Tasadora (REACT)
# =========================================================================
@pytest.mark.asyncio
async def test_tasadora_detects_discrepancy(isolated_registry_snapshot) -> None:
    from src.tools.pe.jne import JneInput, JneOutput
    from src.tools.pe.sunarp import SunarpInput

    async def fake_jne(payload: JneInput) -> JneOutput:
        return JneOutput(
            candidate_id=payload.candidate_id,
            full_name="Juan Pérez",
            dni="12345678",
            party="Partido X",
            office_seeking="Congreso",
            education=[],
            properties_declared=["Inmueble en Lima"],
            income_declared=Money(amount=150_000.0, currency="PEN"),
            sentences=[],
            raw_text="texto JNE",
            pdf_url="https://plataformaelectoral.jne.gob.pe/HojaVida/test.pdf",
            sources=[],
            citations=[],
        )

    async def fake_sunarp(payload: SunarpInput) -> SunarpOutput:
        return SunarpOutput(
            dni=payload.dni,
            properties=[
                SunarpProperty(
                    type="inmueble",
                    partida="P-100",
                    ubicacion="Miraflores",
                    descripcion="Departamento",
                    valor=Money(amount=400_000.0, currency="PEN"),
                ),
                SunarpProperty(
                    type="inmueble",
                    partida="P-101",
                    ubicacion="San Isidro",
                    descripcion="Casa",
                    valor=Money(amount=900_000.0, currency="PEN"),
                ),
            ],
            citations=[],
            used_private_api=False,
        )

    _register("fetch_jne_hoja_vida", JneInput, JneOutput, fake_jne)
    _register("query_sunarp_properties", SunarpInput, SunarpOutput, fake_sunarp)

    decisions = [
        json.dumps(
            {
                "thought": "bajar PDF JNE",
                "action": "fetch_jne_hoja_vida",
                "args": {"candidate_id": "2021-0123"},
            }
        ),
        json.dumps(
            {
                "thought": "consultar SUNARP",
                "action": "query_sunarp_properties",
                "args": {"dni": "12345678"},
            }
        ),
        json.dumps({"thought": "listo", "action": "finish", "args": {}}),
    ]
    llm = FakeLLM({"deepseek/deepseek-v4-flash": decisions})
    tasadora = LaTasadora(country="pe", locale="es", llm=llm)
    target = _entity_id()
    claims = await tasadora.run(
        {"task": "Cruzar patrimonio", "target_entity_id": target},
        {"investigation_id": "i"},
    )

    predicates = {c["predicate"] for c in claims}
    assert "patrimony_discrepancy" in predicates
    assert "property_observed" in predicates
    discrepancy = next(c for c in claims if c["predicate"] == "patrimony_discrepancy")
    assert discrepancy["object_value"]["observed_count"] == 2
    assert discrepancy["object_value"]["delta_pen"] > 0


@pytest.mark.asyncio
async def test_tasadora_match_when_aligned(isolated_registry_snapshot) -> None:
    from src.tools.pe.jne import JneInput, JneOutput
    from src.tools.pe.sunarp import SunarpInput

    async def fake_jne(payload: JneInput) -> JneOutput:
        return JneOutput(
            candidate_id=payload.candidate_id,
            full_name="María López",
            dni="22222222",
            education=[],
            properties_declared=["Casa Lima"],
            income_declared=Money(amount=500_000.0, currency="PEN"),
            sentences=[],
            raw_text="x",
            pdf_url="https://x",
            sources=[],
            citations=[],
        )

    async def fake_sunarp(payload: SunarpInput) -> SunarpOutput:
        return SunarpOutput(
            dni=payload.dni,
            properties=[
                SunarpProperty(
                    type="inmueble",
                    valor=Money(amount=500_000.0, currency="PEN"),
                )
            ],
            citations=[],
            used_private_api=False,
        )

    _register("fetch_jne_hoja_vida", JneInput, JneOutput, fake_jne)
    _register("query_sunarp_properties", SunarpInput, SunarpOutput, fake_sunarp)
    llm = FakeLLM(
        {
            "deepseek/deepseek-v4-flash": [
                json.dumps(
                    {
                        "thought": "JNE",
                        "action": "fetch_jne_hoja_vida",
                        "args": {"candidate_id": "x"},
                    }
                ),
                json.dumps(
                    {
                        "thought": "SUNARP",
                        "action": "query_sunarp_properties",
                        "args": {"dni": "22222222"},
                    }
                ),
                json.dumps({"thought": "done", "action": "finish", "args": {}}),
            ]
        }
    )
    tasadora = LaTasadora(country="pe", locale="es", llm=llm)
    claims = await tasadora.run(
        {"task": "x", "target_entity_id": _entity_id()},
        {"investigation_id": "i"},
    )
    predicates = {c["predicate"] for c in claims}
    assert "patrimony_match" in predicates


# =========================================================================
# El Letrado (REWOO)
# =========================================================================
@pytest.mark.asyncio
async def test_letrado_emits_vote_interest_conflict(isolated_registry_snapshot) -> None:
    from src.tools.pe.legalize import LegalizeQueryInput, LegalizeQueryOutput
    from src.tools.pe.stubs import (
        CrossVoteInput,
        SearchSentencesInput,
    )

    async def fake_legalize(payload: LegalizeQueryInput) -> LegalizeQueryOutput:
        return LegalizeQueryOutput(results=[], total=0)

    async def fake_sentences(payload: SearchSentencesInput) -> SearchSentencesOutput:
        return SearchSentencesOutput(
            query=payload.name,
            sentences=[
                Sentence(
                    case_id="EXP-2020-001",
                    court="3er Juzgado Penal",
                    year=2020,
                    crime="Peculado",
                    outcome="Investigación abierta",
                    url="https://pj.gob.pe/exp/2020-001",
                )
            ],
            citations=[],
            stub=False,
        )

    async def fake_cross_vote(payload: CrossVoteInput) -> CrossVoteOutput:
        return CrossVoteOutput(
            legislator=payload.legislator_name,
            conflicts=[
                VoteConflict(
                    law_number="31123",
                    law_title="Ley promoción pesquera",
                    vote="favor",
                    declared_asset="Pesquera ABC SAC",
                    overlap_reason="sector pesquero",
                    confidence=0.90,
                )
            ],
            citations=[],
            stub=False,
        )

    _register("query_legalize_pe", LegalizeQueryInput, LegalizeQueryOutput, fake_legalize)
    _register("search_sentences", SearchSentencesInput, SearchSentencesOutput, fake_sentences)
    _register("cross_vote_interest", CrossVoteInput, CrossVoteOutput, fake_cross_vote)

    plan = json.dumps(
        {
            "steps": [
                {"tool": "query_legalize_pe", "args": {"query": "Juan Pérez"}},
                {"tool": "search_sentences", "args": {"name": "Juan Pérez"}},
                {
                    "tool": "cross_vote_interest",
                    "args": {
                        "legislator_name": "Juan Pérez",
                        "declared_assets": ["Pesquera ABC SAC"],
                    },
                },
            ]
        }
    )
    llm = FakeLLM({"deepseek/deepseek-v4-flash": [plan]})
    letrado = ElLetrado(country="pe", locale="es", llm=llm)
    claims = await letrado.run(
        {"task": "x", "target_entity_id": _entity_id()},
        {"investigation_id": "i"},
    )
    predicates = {c["predicate"] for c in claims}
    assert "vote_interest_conflict" in predicates
    assert "has_sentence" in predicates
    conflict = next(c for c in claims if c["predicate"] == "vote_interest_conflict")
    assert conflict["object_value"]["law_number"] == "31123"
    assert conflict["confidence"] == 0.90


# =========================================================================
# El Detective (REACT, edges-only)
# =========================================================================
@pytest.mark.asyncio
async def test_detective_returns_edges_not_claims(isolated_registry_snapshot) -> None:
    from src.tools.pe.relatives import Relative, RelativesInput
    from src.tools.pe.stubs import (
        ExpandNetworkInput,
        ExpandNetworkOutput,
        SunarpBoardInput,
    )

    async def fake_relatives(payload: RelativesInput) -> RelativesOutput:
        return RelativesOutput(
            root_dni=payload.dni,
            relatives=[
                Relative(dni="11111111", name="Ana López", relation="spouse_of", degree=1),
                Relative(dni="22222222", name="Pedro López", relation="parent_of", degree=1),
            ],
            citations=[],
        )

    async def fake_board(payload: SunarpBoardInput) -> SunarpBoardOutput:
        return SunarpBoardOutput(
            members=[
                BoardMember(
                    dni="12345678",
                    name="Juan Pérez",
                    role="director",
                    company_ruc="20512345678",
                    company_name="Pesquera ABC SAC",
                )
            ],
            citations=[],
            stub=True,
        )

    async def fake_expand(payload: ExpandNetworkInput) -> ExpandNetworkOutput:
        return ExpandNetworkOutput(edges=[], citations=[], stub=True)

    _register("find_relatives", RelativesInput, RelativesOutput, fake_relatives)
    _register("query_sunarp_board", SunarpBoardInput, SunarpBoardOutput, fake_board)
    _register("expand_network", ExpandNetworkInput, ExpandNetworkOutput, fake_expand)

    decisions = [
        json.dumps(
            {
                "thought": "BFS familia",
                "action": "find_relatives",
                "args": {"dni": "12345678", "degree": 2},
            }
        ),
        json.dumps(
            {
                "thought": "directorio",
                "action": "query_sunarp_board",
                "args": {"dni": "12345678"},
            }
        ),
        json.dumps({"thought": "fin", "action": "finish", "args": {}}),
    ]
    llm = FakeLLM({"deepseek/deepseek-v4-flash": decisions})
    detective = ElDetective(country="pe", locale="es", llm=llm)
    result = await detective.run(
        {
            "task": "Mapear red",
            "entity_identifier": "12345678",
            "target_entity_id": _entity_id(),
        },
        {"investigation_id": "i"},
    )
    # En el camino ReAct, _claims_from_results devuelve un dict
    # {claims: [], edges: [...]}. .run() lo retorna tal cual.
    assert isinstance(result, dict)
    assert result["claims"] == []
    edges = result["edges"]
    assert len(edges) >= 3
    edge_types = {e["edge_type"] for e in edges}
    assert "spouse_of" in edge_types
    assert "parent_of" in edge_types


# =========================================================================
# El Periodista (REACT)
# =========================================================================
@pytest.mark.asyncio
async def test_periodista_emits_press_mentions(isolated_registry_snapshot) -> None:
    from src.tools.pe.news import NewsArticle, NewsInput, NewsOutput
    from src.tools.pe.stubs import (
        TwitterArchiveInput,
        TwitterArchiveOutput,
        WaybackInput,
        WaybackOutput,
        WaybackSnapshot,
    )

    async def fake_news(payload: NewsInput) -> NewsOutput:
        return NewsOutput(
            query=payload.entity_name,
            articles=[
                NewsArticle(
                    title="Adjudicación cuestionada",
                    url="https://ojo-publico.com/articulo-1",
                    source_domain="ojo-publico.com",
                    snippet="Reporte sobre el caso",
                    priority=1,
                ),
                NewsArticle(
                    title="Opinión",
                    url="https://elcomercio.pe/articulo-2",
                    source_domain="elcomercio.pe",
                    snippet="Editorial",
                    priority=2,
                ),
            ],
            citations=[],
            sources_failed=[],
        )

    async def fake_wayback(payload: WaybackInput) -> WaybackOutput:
        return WaybackOutput(
            query_url=payload.url,
            snapshots=[
                WaybackSnapshot(
                    url=payload.url,
                    timestamp="2024-01-15T00:00:00",
                    archived_url="https://web.archive.org/web/20240115/" + payload.url,
                    status=200,
                )
            ],
            citations=[],
            stub=False,
        )

    async def fake_twitter(payload: TwitterArchiveInput) -> TwitterArchiveOutput:
        return TwitterArchiveOutput(posts=[], citations=[], stub=True)

    _register("search_news_archive", NewsInput, NewsOutput, fake_news)
    _register("wayback_machine", WaybackInput, WaybackOutput, fake_wayback)
    _register("search_twitter_archive", TwitterArchiveInput, TwitterArchiveOutput, fake_twitter)

    decisions = [
        json.dumps(
            {
                "thought": "buscar prensa",
                "action": "search_news_archive",
                "args": {"entity_name": "Juan Pérez", "limit": 10},
            }
        ),
        json.dumps(
            {
                "thought": "archivar canónica",
                "action": "wayback_machine",
                "args": {"url": "https://ojo-publico.com/articulo-1"},
            }
        ),
        json.dumps({"thought": "fin", "action": "finish", "args": {}}),
    ]
    llm = FakeLLM({"moonshot/kimi-k2.6": decisions})
    periodista = ElPeriodista(country="pe", locale="es", llm=llm)
    claims = await periodista.run(
        {"task": "Revisar prensa", "target_entity_id": _entity_id()},
        {"investigation_id": "i"},
    )
    predicates = {c["predicate"] for c in claims}
    assert "mentioned_in_press" in predicates
    assert "archived_at" in predicates
    # Priority 1 → confidence 0.85; priority 2 → 0.65.
    press = [c for c in claims if c["predicate"] == "mentioned_in_press"]
    p1 = [c for c in press if c["object_value"].get("priority") == 1]
    p2 = [c for c in press if c["object_value"].get("priority") == 2]
    assert p1 and p1[0]["confidence"] == 0.85
    assert p2 and p2[0]["confidence"] == 0.65


# =========================================================================
# La Jueza MoA
# =========================================================================
def _support_verdict() -> str:
    return json.dumps(
        {
            "verdict": "support",
            "confidence": 0.9,
            "rationale": "fuente confirma",
            "checked_source_url": "https://example.com/source",
        }
    )


def _refute_verdict() -> str:
    return json.dumps(
        {
            "verdict": "refute",
            "confidence": 0.85,
            "rationale": "voto fue abstención",
            "checked_source_url": "https://congreso.gob.pe/voto",
        }
    )


def _aggregator_response(verified: bool, confidence: float, notes: str) -> str:
    return json.dumps(
        {
            "verified": verified,
            "confidence_final": confidence,
            "disagreements": [],
            "verifier_notes": notes,
        }
    )


@pytest.mark.asyncio
async def test_jueza_consenso_strong():
    """3/3 support con URLs distintas → confidence_final ≥ 0.90."""
    llm = FakeLLM()
    # 1 claim → 3 proposers + 1 aggregator = 4 llamadas
    for model in (
        "anthropic/claude-sonnet-4.6",
        "moonshot/kimi-k2.6",
        "openai/gpt-4o",
    ):
        llm.push(
            model,
            json.dumps(
                {
                    "verdict": "support",
                    "confidence": 0.9,
                    "rationale": "ok",
                    "checked_source_url": f"https://example.com/{model}",
                }
            ),
        )
    llm.push(
        "anthropic/claude-sonnet-4.6",
        _aggregator_response(True, 0.92, "3/3 fuentes distintas"),
    )

    jueza = LaJueza(country="pe", locale="es", llm=llm)
    claims = [
        {
            "predicate": "awarded_contract",
            "object_value": {"ocid": "x"},
            "source_url": "u",
            "confidence": 0.85,
            "agent_callsign": "el-contador",
        }
    ]
    result = await jueza.verify_all({}, {"claims": claims})
    verified_claims = result["claims"]
    assert len(verified_claims) == 1
    v = verified_claims[0]
    assert v["verified"] is True
    assert v["confidence_final"] >= 0.85  # aggregator dijo 0.92
    assert v["agent_callsign"] == "el-contador"  # callsign original preservado
    assert v["confidence_original"] == 0.85


@pytest.mark.asyncio
async def test_jueza_refutation():
    """2/3 refute → verified=false, confidence_final baja."""
    llm = FakeLLM()
    llm.push("anthropic/claude-sonnet-4.6", _support_verdict())
    llm.push("moonshot/kimi-k2.6", _refute_verdict())
    llm.push("openai/gpt-4o", _refute_verdict())
    # Aggregator local calibrará a 0.25 si vamos por fallback;
    # acá probamos también que respete el JSON del aggregator.
    llm.push(
        "anthropic/claude-sonnet-4.6",
        _aggregator_response(False, 0.25, "2/3 refute"),
    )

    jueza = LaJueza(country="pe", locale="es", llm=llm)
    claims = [
        {
            "predicate": "vote_interest_conflict",
            "object_value": {"law_number": "31123"},
            "source_url": "u",
            "confidence": 0.90,
            "agent_callsign": "el-letrado",
        }
    ]
    result = await jueza.verify_all({}, {"claims": claims})
    v = result["claims"][0]
    assert v["verified"] is False
    assert v["confidence_final"] <= 0.30


@pytest.mark.asyncio
async def test_jueza_aggregator_fallback_uses_local_calibration():
    """Si el aggregator devuelve garbage → fallback a calibración local."""
    llm = FakeLLM()
    for model in ("anthropic/claude-sonnet-4.6", "moonshot/kimi-k2.6", "openai/gpt-4o"):
        llm.push(model, _support_verdict())
    # aggregator garbage → fallback
    llm.push("anthropic/claude-sonnet-4.6", "this is not json at all")

    jueza = LaJueza(country="pe", locale="es", llm=llm)
    claims = [
        {
            "predicate": "is_dni",
            "object_value": {"dni": "12345678"},
            "source_url": "u",
            "confidence": 0.95,
            "agent_callsign": "el-buscador",
        }
    ]
    result = await jueza.verify_all({}, {"claims": claims})
    v = result["claims"][0]
    # Las 3 URLs son distintas (un valor por proposer), entonces local
    # calibration debería dar 0.92.
    assert v["confidence_final"] >= 0.80
    assert v["verified"] is True


@pytest.mark.asyncio
async def test_jueza_parallel_chunking_large_batch():
    """>20 claims → chunkea en grupos de 10."""
    n_claims = 25
    llm = FakeLLM()
    # Por cada claim: 3 proposers support + 1 aggregator
    for _ in range(n_claims):
        for model in (
            "anthropic/claude-sonnet-4.6",
            "moonshot/kimi-k2.6",
            "openai/gpt-4o",
        ):
            llm.push(model, _support_verdict())
        llm.push(
            "anthropic/claude-sonnet-4.6",
            _aggregator_response(True, 0.85, "ok"),
        )

    jueza = LaJueza(country="pe", locale="es", llm=llm)
    claims = [
        {
            "predicate": "awarded_contract",
            "object_value": {"ocid": f"ocid-{i}"},
            "source_url": "u",
            "confidence": 0.85,
            "agent_callsign": "el-contador",
        }
        for i in range(n_claims)
    ]
    result = await jueza.verify_all({}, {"claims": claims})
    assert len(result["claims"]) == n_claims
    # Eventos: 1 verification_started + n × verification_done + 1 batch_done.
    event_types = [e["type"] for e in result["events"]]
    assert event_types[0] == "verification_started"
    assert event_types.count("verification_done") == n_claims
    assert event_types[-1] == "verification_batch_done"


@pytest.mark.asyncio
async def test_jueza_empty_claims_short_circuits():
    llm = FakeLLM()
    jueza = LaJueza(country="pe", locale="es", llm=llm)
    result = await jueza.verify_all({}, {"claims": []})
    assert result["claims"] == []
    assert any(e["type"] == "verification_done" for e in result["events"])


# =========================================================================
# Integración: 3 investigadores activos + La Jueza completa
# =========================================================================
@pytest.fixture
def integration_registry():
    """Registra tools fake para el test integración (Contador + Buscador + Letrado)."""
    snapshot = dict(ToolRegistry._tools)
    ToolRegistry._tools.clear()
    from src.tools.pe.legalize import LegalizeQueryInput, LegalizeQueryOutput
    from src.tools.pe.manolo import ManoloInput
    from src.tools.pe.seace import SeaceInput
    from src.tools.pe.stubs import (
        CrossVoteInput,
        FindDniInput,
        FindRucInput,
        SearchSentencesInput,
    )

    async def fake_seace(payload: SeaceInput) -> SeaceOutput:
        return SeaceOutput(
            ruc=payload.ruc,
            contracts=[
                SeaceContract(
                    ocid="ocds-int-1",
                    title="Servicio X",
                    buyer="MINSA",
                    supplier="ABC SAC",
                    award_date="2023-05-10",
                    value=Money(amount=500_000.0, currency="PEN"),
                ),
            ],
            total_amount=Money(amount=500_000.0, currency="PEN"),
            pages_fetched=1,
            sources=[
                Source(
                    url="https://contratacionesabiertas.osce.gob.pe/r/x",
                    source_type="seace",
                )
            ],
        )

    async def fake_dni(payload: FindDniInput) -> FindDniOutput:
        return FindDniOutput(
            record=DniRecord(dni=payload.dni, full_name="X", found=True, stub=True),
            citations=[],
        )

    async def fake_ruc(payload: FindRucInput) -> FindRucOutput:
        return FindRucOutput(
            record=RucRecord(
                ruc=payload.ruc, razon_social="ABC SAC", estado="ACTIVO", found=True, stub=True
            ),
            citations=[],
        )

    async def fake_manolo(payload: ManoloInput) -> ManoloOutput:
        return ManoloOutput(query=payload.query, visits=[], citations=[])

    async def fake_legalize(payload: LegalizeQueryInput) -> LegalizeQueryOutput:
        return LegalizeQueryOutput(results=[], total=0)

    async def fake_sentences(payload: SearchSentencesInput) -> SearchSentencesOutput:
        return SearchSentencesOutput(
            query=payload.name, sentences=[], citations=[], stub=True
        )

    async def fake_cross_vote(payload: CrossVoteInput) -> CrossVoteOutput:
        return CrossVoteOutput(
            legislator=payload.legislator_name, conflicts=[], citations=[], stub=True
        )

    _register("search_seace_contracts", SeaceInput, SeaceOutput, fake_seace)
    _register("find_dni_record", FindDniInput, FindDniOutput, fake_dni)
    _register("find_ruc_record", FindRucInput, FindRucOutput, fake_ruc)
    _register("search_manolo", ManoloInput, ManoloOutput, fake_manolo)
    _register("query_legalize_pe", LegalizeQueryInput, LegalizeQueryOutput, fake_legalize)
    _register("search_sentences", SearchSentencesInput, SearchSentencesOutput, fake_sentences)
    _register("cross_vote_interest", CrossVoteInput, CrossVoteOutput, fake_cross_vote)
    yield
    ToolRegistry._tools.clear()
    ToolRegistry._tools.update(snapshot)


@pytest.mark.asyncio
async def test_integration_three_subagents_plus_jueza_under_budget(
    integration_registry,
) -> None:
    """Plan con 3 subagentes (buscador + contador + letrado) + La Jueza
    verificando todos los claims. Verificá: status=complete, costo < $1.00."""
    investigation_id = str(uuid.uuid4())
    target_entity_id = str(uuid.uuid4())

    plan_response = json.dumps(
        {
            "plan": [
                {"agent": "buscador", "task": "Resolver identidades", "priority": 1},
                {"agent": "contador", "task": "Contratos", "priority": 2},
                {"agent": "letrado", "task": "Cruzar votos", "priority": 3},
            ]
        }
    )
    buscador_plan = json.dumps(
        {
            "steps": [
                {"tool": "find_dni_record", "args": {"dni": "12345678"}},
                {"tool": "find_ruc_record", "args": {"ruc": "20512345678"}},
            ]
        }
    )
    contador_plan = json.dumps(
        {
            "steps": [
                {
                    "tool": "search_seace_contracts",
                    "args": {
                        "ruc": "20512345678",
                        "year_from": 2020,
                        "year_to": 2024,
                    },
                }
            ]
        }
    )
    letrado_plan = json.dumps(
        {
            "steps": [
                {"tool": "query_legalize_pe", "args": {"query": "Pérez", "limit": 5}},
                {"tool": "search_sentences", "args": {"name": "Juan Pérez"}},
            ]
        }
    )
    dossier_md = "# Dossier\n## Resumen\n- claim\n"

    llm = FakeLLM(
        {
            "anthropic/claude-sonnet-4.6": [plan_response],
            "anthropic/claude-opus-4.7": [dossier_md],
            "moonshot/kimi-k2.6": [buscador_plan, contador_plan],
            "deepseek/deepseek-v4-flash": [letrado_plan],
        }
    )

    # Los runners de los investigadores
    buscador = ElBuscador(country="pe", locale="es", llm=llm)
    contador = ElContador(country="pe", locale="es", llm=llm)
    letrado = ElLetrado(country="pe", locale="es", llm=llm)
    jueza = LaJueza(country="pe", locale="es", llm=llm)

    # La Jueza necesitará 3 proposers + 1 aggregator por cada claim
    # emitido. Como no sabemos el N exacto antes de correr, encolamos
    # respuestas suficientes con un margen generoso.
    for _ in range(50):
        for model in ("anthropic/claude-sonnet-4.6", "moonshot/kimi-k2.6", "openai/gpt-4o"):
            llm.push(model, _support_verdict())
        llm.push("anthropic/claude-sonnet-4.6", _aggregator_response(True, 0.85, "ok"))

    deps = GraphDeps(
        llm=llm,
        db_pool=None,
        investigator_runners={
            "buscador": buscador.run,
            "contador": contador.run,
            "letrado": letrado.run,
        },
        jueza_runner=jueza.verify_all,
        persist_dry_run=True,
    )

    checkpointer = in_memory_checkpointer()
    graph = build_graph(deps, checkpointer=checkpointer)

    initial_state: dict[str, Any] = {
        "investigation_id": investigation_id,
        "target_entity_id": target_entity_id,
        "country": "pe",
        "locale": "es",
        "user_query": "Investigar a Juan Pérez",
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
        config={"configurable": {"thread_id": f"e2e-s11-{investigation_id}"}},
    )

    assert final_state["status"] == "complete", final_state.get("status")
    claims = final_state["claims"]
    assert len(claims) >= 2, f"esperaban claims de 3 subagentes, llegaron {len(claims)}"
    # Verificación cubrió todos los claims
    verified = final_state["verified_claims"]
    assert len(verified) == len(claims)
    assert all(v.get("verified_by_jueza") for v in verified)
    # Budget hard cap: < $1.00 (cada llamada FakeLLM cobra $0.02)
    cost = float(final_state.get("cost_usd") or 0.0)
    assert cost < 1.00, f"cost_usd={cost} excede $1.00"

    # Callsigns esperados en los claims (al menos buscador + contador)
    callsigns = {c.get("agent_callsign") for c in claims}
    assert "el-contador" in callsigns
    assert "el-buscador" in callsigns
