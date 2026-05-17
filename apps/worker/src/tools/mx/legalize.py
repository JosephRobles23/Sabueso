"""query_legalize_mx — corpus legal mexicano (Modo Preview, dataset estático).

Para S-18 alcanza un mock con 10 leyes federales relevantes. Cuando exista
un connector real a LeyesNet / DOF / Cámara de Diputados, este módulo se
reemplaza manteniendo la misma signature.

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
    country: str = "mx"


class LegalizeQueryOutput(BaseModel):
    results: list[Citation]
    total: int


_FALLBACK_LAWS: tuple[dict[str, Any], ...] = (
    {
        "law_id": "cpeum",
        "title": "Constitución Política de los Estados Unidos Mexicanos",
        "summary": (
            "Carta magna mexicana. Define la forma de gobierno republicana, "
            "federal y representativa, garantías individuales y división de poderes."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CPEUM.pdf",
        "year": 1917,
        "materias": ["constitucional", "garantías individuales"],
    },
    {
        "law_id": "lgtaip",
        "title": "Ley General de Transparencia y Acceso a la Información Pública",
        "summary": (
            "Marco federal de transparencia. Crea el SNT y obliga a sujetos "
            "obligados a publicar información de oficio. Aplica al INAI."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LGTAIP.pdf",
        "year": 2015,
        "materias": ["transparencia", "acceso a la información", "INAI"],
    },
    {
        "law_id": "lgrsa",
        "title": "Ley General de Responsabilidades Administrativas",
        "summary": (
            "Define faltas administrativas graves (cohecho, peculado, "
            "tráfico de influencias) y el régimen sancionador para servidores "
            "públicos. Sustento del Sistema Nacional Anticorrupción (SNA)."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LGRA.pdf",
        "year": 2016,
        "materias": ["responsabilidades administrativas", "SNA", "anticorrupción"],
    },
    {
        "law_id": "ldfsm",
        "title": "Ley de Adquisiciones, Arrendamientos y Servicios del Sector Público",
        "summary": (
            "Regula compras públicas federales: licitación pública, invitación "
            "restringida y adjudicación directa. Aplica CompraNet."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LAASSP.pdf",
        "year": 2000,
        "materias": ["compras públicas", "licitación", "CompraNet"],
    },
    {
        "law_id": "lfpa",
        "title": "Ley Federal de Procedimiento Administrativo",
        "summary": (
            "Regula los actos, procedimientos y resoluciones de la "
            "administración pública federal en su relación con particulares."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/112.pdf",
        "year": 1994,
        "materias": ["procedimiento administrativo", "actos administrativos"],
    },
    {
        "law_id": "lfecm",
        "title": "Ley Federal contra la Delincuencia Organizada",
        "summary": (
            "Define delincuencia organizada y aumenta penas para delitos "
            "cometidos por grupos estructurados (lavado, narcomenudeo, "
            "huachicol, secuestro)."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFCDO.pdf",
        "year": 1996,
        "materias": ["delincuencia organizada", "código penal"],
    },
    {
        "law_id": "lopem",
        "title": "Ley Orgánica del Poder Ejecutivo Federal",
        "summary": (
            "Estructura el gabinete federal mexicano: secretarías de Estado, "
            "Consejería Jurídica, Fiscalía y entidades paraestatales."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/153.pdf",
        "year": 1976,
        "materias": ["poder ejecutivo", "secretarías de Estado"],
    },
    {
        "law_id": "lgipd",
        "title": "Ley General de Instituciones y Procedimientos Electorales",
        "summary": (
            "Regula la organización, financiamiento y fiscalización de "
            "partidos políticos y elecciones federales (INE)."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LGIPE.pdf",
        "year": 2014,
        "materias": ["electoral", "INE", "partidos políticos"],
    },
    {
        "law_id": "lfprh",
        "title": "Ley Federal de Presupuesto y Responsabilidad Hacendaria",
        "summary": (
            "Regula la elaboración, ejercicio y control del Presupuesto de "
            "Egresos de la Federación; principios de eficiencia, transparencia "
            "y rendición de cuentas."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPRH.pdf",
        "year": 2006,
        "materias": ["presupuesto", "hacienda", "rendición de cuentas"],
    },
    {
        "law_id": "lfpda",
        "title": "Ley Federal de Protección de Datos Personales en Posesión de los Particulares",
        "summary": (
            "Marco de protección de datos personales (privacidad). Define "
            "principios, derechos ARCO y régimen sancionador del INAI."
        ),
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf",
        "year": 2010,
        "materias": ["protección de datos", "privacidad", "derechos ARCO"],
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
                    "country": "mx",
                    "year": law.get("year"),
                    "materias": law.get("materias", []),
                    "source": "fallback-dataset",
                },
            )
        )
    return out


@ToolRegistry.register(
    country="mx",
    input_model=LegalizeQueryInput,
    output_model=LegalizeQueryOutput,
    cache_ttl=7 * 24 * 3600,
    tags=("legal", "corpus", "preview"),
)
async def query_legalize_mx(payload: LegalizeQueryInput) -> LegalizeQueryOutput:
    """Búsqueda en dataset estático de leyes federales mexicanas.

    Modo Preview (S-18): 10 leyes hardcoded. Reemplazar por conector real
    (LeyesNet / Cámara de Diputados) cuando esté disponible.
    """
    results = _search_mock(payload.query, payload.limit)
    return LegalizeQueryOutput(results=results, total=len(results))


__all__ = ["query_legalize_mx", "LegalizeQueryInput", "LegalizeQueryOutput"]
