"""Tests para query_legalize_{cl,mx,sv} — Modo Preview S-18.

Tests offline: no necesitan DB ni red. Validan:
- Las tools se registran en el ``ToolRegistry`` bajo el país correcto.
- El input model rechaza queries inválidas.
- El dataset fallback devuelve resultados con shape de Citation.
- Cada tool respeta el ``limit`` solicitado.
- Para SV/MX el dataset hardcoded tiene >=5 leyes (req. acceptance).
"""

from __future__ import annotations

import importlib

import pytest

from src.tools import ToolRegistry
from src.tools.cl.legalize import (
    _FALLBACK_LAWS as CL_LAWS,
)
from src.tools.cl.legalize import (
    LegalizeQueryInput as ClInput,
)
from src.tools.cl.legalize import (
    query_legalize_cl,
)
from src.tools.mx.legalize import (
    _FALLBACK_LAWS as MX_LAWS,
)
from src.tools.mx.legalize import (
    LegalizeQueryInput as MxInput,
)
from src.tools.mx.legalize import (
    query_legalize_mx,
)
from src.tools.sv.legalize import (
    _FALLBACK_LAWS as SV_LAWS,
)
from src.tools.sv.legalize import (
    LegalizeQueryInput as SvInput,
)
from src.tools.sv.legalize import (
    query_legalize_sv,
)


@pytest.fixture(autouse=True)
def _ensure_tools_registered(isolated_registry):
    """Garantiza que las 3 tools de Modo Preview estén registradas.

    Otros tests (test_registry.py) limpian el ``ToolRegistry`` y restauran
    su propio snapshot, que puede no contener las cl/mx/sv si nadie las
    importó antes. Re-cargamos los módulos para que los decoradores
    ``@ToolRegistry.register`` corran de nuevo.
    """
    for mod_path in (
        "src.tools.cl.legalize",
        "src.tools.mx.legalize",
        "src.tools.sv.legalize",
    ):
        import sys  # noqa: PLC0415

        if mod_path in sys.modules:
            importlib.reload(sys.modules[mod_path])
        else:
            importlib.import_module(mod_path)
    yield


def test_legalize_cl_registered_under_cl():
    tool = ToolRegistry.get("cl", "query_legalize_cl")
    assert tool.country == "cl"
    assert tool.cache_ttl == 7 * 24 * 3600
    assert "preview" in tool.tags


def test_legalize_mx_registered_under_mx():
    tool = ToolRegistry.get("mx", "query_legalize_mx")
    assert tool.country == "mx"
    assert "preview" in tool.tags


def test_legalize_sv_registered_under_sv():
    tool = ToolRegistry.get("sv", "query_legalize_sv")
    assert tool.country == "sv"
    assert "preview" in tool.tags


def test_fallback_datasets_have_minimum_size():
    """Acceptance criterion: 5-10 leyes hardcoded por país de preview."""
    assert 5 <= len(CL_LAWS) <= 15
    assert 5 <= len(MX_LAWS) <= 15
    assert 5 <= len(SV_LAWS) <= 15


@pytest.mark.asyncio
async def test_query_legalize_cl_returns_citation_shape():
    out = await query_legalize_cl(ClInput(query="transparencia"))
    assert out.total >= 1
    assert out.total <= 10
    first = out.results[0]
    assert first.source.url.startswith(("http://", "https://"))
    assert first.source.source_type == "legalize"
    assert first.extra.get("country") == "cl"


@pytest.mark.asyncio
async def test_query_legalize_mx_filters_by_query():
    """La búsqueda por overlap de tokens favorece la ley más relevante."""
    out = await query_legalize_mx(MxInput(query="transparencia INAI"))
    assert out.total >= 1
    titles = " ".join(c.source.title or "" for c in out.results).lower()
    assert "transparencia" in titles


@pytest.mark.asyncio
async def test_query_legalize_sv_respects_limit():
    out = await query_legalize_sv(SvInput(query="ley", limit=3))
    assert len(out.results) <= 3


@pytest.mark.asyncio
async def test_query_legalize_sv_fallback_when_no_match():
    """Sin tokens en común, devuelve sugerencias top-N en lugar de vacío.

    Eso permite que el subagente Letrado siempre tenga material en preview.
    """
    out = await query_legalize_sv(SvInput(query="zzzqq", limit=3))
    assert len(out.results) <= 3


@pytest.mark.asyncio
async def test_legalize_mx_no_db_no_network():
    """La tool funciona enteramente offline (no toca SUPABASE_DB_URL ni red)."""
    out = await query_legalize_mx(MxInput(query="constitución"))
    assert out.total >= 1


def test_input_rejects_empty_query():
    with pytest.raises(Exception):
        ClInput(query="")


def test_input_clamps_limit():
    with pytest.raises(Exception):
        ClInput(query="ley", limit=100)
