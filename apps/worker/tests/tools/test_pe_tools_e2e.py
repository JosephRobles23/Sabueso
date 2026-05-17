"""E2E tests para las 8 tools PE.

**Cómo correr:**

    SABUESO_RUN_E2E=1 pytest tests/tools/test_pe_tools_e2e.py -m e2e -v

Sin la env var, todos los tests se skipean (ver ``conftest.py``).

Cada test apunta a un caso público real:
- RUC del MINSA (20131367602) para SEACE.
- DNI público (00000001) para Manolo / SUNARP / find_relatives — fail gracefully
  esperado en algunos.
- Candidato JNE ejemplo de elecciones 2021 (id 187395 cuando estaba activo).
- Nombre público (e.g. "Pedro Castillo") para news_archive y El Peruano.

Los tests verifican *contrato* (shape, schemas, errores tipados), no
contenidos específicos — los datasets cambian.
"""

from __future__ import annotations

import pytest

from src.tools import ToolRegistry, load_pe_tools
from src.tools.errors import RateLimitedError, SourceUnavailableError, ToolError
from src.tools.pe import apply_pe_rate_limits

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True, scope="module")
def _ensure_registry_loaded():
    load_pe_tools()
    apply_pe_rate_limits()
    yield


def _expect_tool_error_or_ok(coro):
    """Helper: muchas fuentes están caídas con cierta frecuencia; un fallo
    tipado (``ToolError``) cuenta como pass del contrato. Lo que NO debe pasar
    es un AttributeError / TypeError / etc."""
    import asyncio  # noqa: PLC0415

    try:
        return asyncio.get_event_loop().run_until_complete(coro)
    except ToolError as exc:
        pytest.skip(f"upstream unavailable (expected variance): {exc}")


@pytest.mark.asyncio
async def test_query_legalize_pe_contract():
    """Caso: query simple. Si no hay DB configurada devuelve results=[]."""
    from src.tools.pe.legalize import LegalizeQueryInput, query_legalize_pe

    out = await query_legalize_pe(LegalizeQueryInput(query="contraloría general"))
    assert out.total == len(out.results)
    for r in out.results:
        assert r.text
        assert r.source.source_type == "legalize"


@pytest.mark.asyncio
async def test_search_seace_contracts_real_ruc():
    """RUC del MINSA (20131367602) — entidad pública gigante, garantiza data."""
    from src.tools.pe.seace import SeaceInput, search_seace_contracts

    try:
        out = await search_seace_contracts(
            SeaceInput(ruc="20131367602", year_from=2023, year_to=2024)
        )
    except (SourceUnavailableError, RateLimitedError) as exc:
        pytest.skip(f"SEACE upstream: {exc}")
    assert out.ruc == "20131367602"
    assert out.total_amount.currency == "PEN"
    assert out.pages_fetched >= 1
    # MINSA típicamente tiene miles de contratos, no garantizamos cantidad mínima
    # porque las APIs OCDS de OECE cambian de path; el contrato suficiente es
    # que pages_fetched ≥ 1 y la lista existe.
    assert isinstance(out.contracts, list)


@pytest.mark.asyncio
async def test_search_manolo_by_name():
    """Búsqueda por nombre público. La página puede cambiar selectors → puede
    retornar visits=[]; eso sigue siendo un pass del contrato."""
    from src.tools.pe.manolo import ManoloInput, search_manolo

    try:
        out = await search_manolo(ManoloInput(query="Pedro Castillo", limit=10))
    except (SourceUnavailableError, RateLimitedError) as exc:
        pytest.skip(f"Manolo upstream: {exc}")
    assert out.query == "Pedro Castillo"
    assert isinstance(out.visits, list)
    for v in out.visits:
        assert v.visitor or v.entity  # al menos un campo poblado


@pytest.mark.asyncio
async def test_fetch_jne_hoja_vida_contract():
    """Si no tenemos un candidate_id válido el handler debe fallar con
    ``ToolError`` (no con AttributeError)."""
    from src.tools.pe.jne import JneInput, fetch_jne_hoja_vida

    with pytest.raises(ToolError):
        await fetch_jne_hoja_vida(JneInput(candidate_id="000000000"))


@pytest.mark.asyncio
async def test_query_sunarp_properties_graceful():
    from src.tools.pe.sunarp import SunarpInput, query_sunarp_properties

    out = await query_sunarp_properties(SunarpInput(dni="00000001"))
    assert out.dni == "00000001"
    assert isinstance(out.properties, list)
    assert len(out.citations) >= 1  # al menos disclaimer del portal


@pytest.mark.asyncio
async def test_find_relatives_with_unknown_dni():
    from src.tools.pe.relatives import RelativesInput, find_relatives

    out = await find_relatives(RelativesInput(dni="00000001", degree=2))
    assert out.root_dni == "00000001"
    assert isinstance(out.relatives, list)


@pytest.mark.asyncio
async def test_search_el_peruano_real_query():
    from src.tools.pe.el_peruano import ElPeruanoInput, search_el_peruano

    try:
        out = await search_el_peruano(ElPeruanoInput(query="ministerio de salud", limit=5))
    except (SourceUnavailableError, RateLimitedError) as exc:
        pytest.skip(f"El Peruano upstream: {exc}")
    assert isinstance(out.results, list)
    for r in out.results:
        assert r.title
        assert r.url.startswith("http")


@pytest.mark.asyncio
async def test_search_news_archive_real_query():
    from src.tools.pe.news import NewsInput, search_news_archive

    out = await search_news_archive(NewsInput(entity_name="Pedro Castillo", limit=10))
    assert out.query == "Pedro Castillo"
    assert isinstance(out.articles, list)
    # Wayback casi siempre devuelve algo; idl/ojo/convoca pueden fallar.
    assert len(out.articles) + len(out.sources_failed) >= 1


@pytest.mark.asyncio
async def test_all_eight_tools_registered():
    """Verifica que ``load_pe_tools()`` registra exactamente las 8 esperadas."""
    expected = {
        "query_legalize_pe",
        "search_seace_contracts",
        "search_manolo",
        "fetch_jne_hoja_vida",
        "query_sunarp_properties",
        "find_relatives",
        "search_el_peruano",
        "search_news_archive",
    }
    pe_tools = {t.name for t in ToolRegistry.get_tools_for("pe")}
    missing = expected - pe_tools
    assert not missing, f"missing PE tools: {missing}"


@pytest.mark.asyncio
async def test_mcp_manifest_includes_all_pe_tools():
    manifest = ToolRegistry.export_as_mcp(country="pe")
    names = {t["name"] for t in manifest["tools"]}
    assert "search_seace_contracts" in names
    assert all("inputSchema" in t for t in manifest["tools"])
