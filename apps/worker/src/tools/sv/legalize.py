"""query_legalize_sv — corpus legal salvadoreño (Modo Preview, dataset estático).

Para S-18 alcanza un mock con 10 leyes relevantes de El Salvador. Cuando
exista un connector real (Asamblea Legislativa, gob.sv, OEPS) reemplazar
este módulo manteniendo la signature.

TTL cache: 7 días.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ..pe._common import Citation, Source
from ..registry import ToolRegistry


class LegalizeQueryInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    semantic: bool = True
    limit: int = Field(10, ge=1, le=50)
    country: str = "sv"


class LegalizeQueryOutput(BaseModel):
    results: list[Citation]
    total: int


_FALLBACK_LAWS: tuple[dict[str, Any], ...] = (
    {
        "law_id": "constitucion-sv",
        "title": "Constitución de la República de El Salvador",
        "summary": (
            "Carta fundamental salvadoreña. Define forma de gobierno, "
            "derechos individuales, organización del Estado y régimen "
            "municipal."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/249",
        "year": 1983,
        "materias": ["constitucional", "derechos fundamentales"],
    },
    {
        "law_id": "laip-sv",
        "title": "Ley de Acceso a la Información Pública (LAIP)",
        "summary": (
            "Garantiza el derecho de acceso a la información pública. Crea el "
            "Instituto de Acceso a la Información Pública (IAIP) y obligaciones "
            "de transparencia activa."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/237",
        "year": 2011,
        "materias": ["transparencia", "acceso a la información", "IAIP"],
    },
    {
        "law_id": "lacap-sv",
        "title": "Ley de Adquisiciones y Contrataciones de la Administración Pública (LACAP)",
        "summary": (
            "Regula compras del sector público salvadoreño: licitación, "
            "concurso, contratación directa y libre gestión. Vinculada a "
            "COMPRASAL."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/261",
        "year": 2000,
        "materias": ["compras públicas", "contratación", "COMPRASAL"],
    },
    {
        "law_id": "letp-sv",
        "title": "Ley de Ética Gubernamental",
        "summary": (
            "Establece principios éticos y deberes para los servidores "
            "públicos. Crea el Tribunal de Ética Gubernamental (TEG) y la "
            "declaración patrimonial."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/239",
        "year": 2011,
        "materias": ["ética", "patrimonio", "TEG"],
    },
    {
        "law_id": "lcla-sv",
        "title": "Ley contra el Lavado de Dinero y de Activos",
        "summary": (
            "Tipifica el lavado de dinero y crea la Unidad de Investigación "
            "Financiera (UIF) dentro de la Fiscalía General."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/250",
        "year": 1998,
        "materias": ["lavado de dinero", "UIF", "delitos financieros"],
    },
    {
        "law_id": "ley-extincion-dominio-sv",
        "title": (
            "Ley Especial de Extinción de Dominio y de la Administración de "
            "los Bienes de Origen o Destinación Ilícita"
        ),
        "summary": (
            "Permite al Estado extinguir el dominio de bienes de origen o "
            "destinación ilícita sin necesidad de condena penal previa."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/259",
        "year": 2013,
        "materias": ["extinción de dominio", "anticorrupción", "bienes"],
    },
    {
        "law_id": "codigo-penal-sv",
        "title": "Código Penal de El Salvador",
        "summary": (
            "Cuerpo normativo de delitos y penas. Tipifica peculado, cohecho, "
            "negociaciones ilícitas y enriquecimiento ilícito de funcionarios."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/258",
        "year": 1997,
        "materias": ["código penal", "cohecho", "peculado"],
    },
    {
        "law_id": "ley-partidos-politicos-sv",
        "title": "Ley de Partidos Políticos",
        "summary": (
            "Regula constitución, financiamiento, fiscalización y democracia "
            "interna de los partidos políticos. Aplica el TSE."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/238",
        "year": 2013,
        "materias": ["partidos políticos", "financiamiento político", "TSE"],
    },
    {
        "law_id": "lcc-sv",
        "title": "Ley de la Corte de Cuentas de la República",
        "summary": (
            "Norma la fiscalización del manejo de fondos públicos. Faculta a "
            "la CCR para auditar, juzgar y sancionar funcionarios."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/241",
        "year": 1995,
        "materias": ["fiscalización", "Corte de Cuentas", "auditoría"],
    },
    {
        "law_id": "ley-proteccion-victimas-sv",
        "title": "Ley Especial para la Protección de Víctimas y Testigos",
        "summary": (
            "Protege a víctimas y testigos en procesos penales. Útil para "
            "casos de corrupción y delincuencia organizada."
        ),
        "url": "https://www.asamblea.gob.sv/decretos/details/256",
        "year": 2006,
        "materias": ["víctimas", "testigos", "protección"],
    },
)


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    return {w.casefold() for w in _WORD_RE.findall(text)}


def _search_mock(query: str, limit: int) -> list[Citation]:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for law in _FALLBACK_LAWS:
        haystack = " ".join(
            [
                law["title"],
                law["summary"],
                " ".join(law.get("materias", [])),
            ]
        )
        l_tokens = _tokenize(haystack)
        overlap = len(q_tokens & l_tokens)
        if overlap == 0:
            continue
        score = overlap / max(len(q_tokens), 1)
        scored.append((score, law))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        scored = [(0.0, law) for law in _FALLBACK_LAWS[:limit]]

    out: list[Citation] = []
    for score, law in scored[:limit]:
        out.append(
            Citation(
                text=f"{law['title']} — {law['summary']}"[:500],
                source=Source(
                    url=law["url"],
                    source_type="legalize",
                    title=law["title"],
                ),
                extra={
                    "law_id": law["law_id"],
                    "score": score,
                    "country": "sv",
                    "year": law.get("year"),
                    "materias": law.get("materias", []),
                    "source": "fallback-dataset",
                },
            )
        )
    return out


@ToolRegistry.register(
    country="sv",
    input_model=LegalizeQueryInput,
    output_model=LegalizeQueryOutput,
    cache_ttl=7 * 24 * 3600,
    tags=("legal", "corpus", "preview"),
)
async def query_legalize_sv(payload: LegalizeQueryInput) -> LegalizeQueryOutput:
    """Búsqueda en dataset estático de leyes salvadoreñas.

    Modo Preview (S-18): 10 leyes hardcoded. Reemplazar por conector real
    a la Asamblea Legislativa cuando esté disponible.
    """
    results = _search_mock(payload.query, payload.limit)
    return LegalizeQueryOutput(results=results, total=len(results))


__all__ = ["query_legalize_sv", "LegalizeQueryInput", "LegalizeQueryOutput"]
