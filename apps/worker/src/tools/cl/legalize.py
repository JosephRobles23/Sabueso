"""query_legalize_cl — corpus legalize-cl (BCN Chile / Ley Chile).

Estrategia:
1. Si hay DB con leyes ``country='cl'`` ingestadas (S-15 futuro), se hace
   búsqueda semántica con pgvector + fallback full-text (idéntico a
   ``pe.legalize``).
2. Si la DB no devuelve nada (corpus aún no ingestado o sin acceso),
   fallback a un dataset hardcoded de leyes chilenas relevantes para el
   demo. Suficiente para Modo Preview (S-18) — el banner del frontend
   advierte al usuario.

Cuando S-15-cl se ejecute con ``LEGALIZE_CL_REPO_URL=https://github.com/
crafter-research/legalize-cl.git`` (o el equivalente Crafter), este flow
empezará a devolver resultados reales sin tocar la tool.

TTL cache: 7 días (corpus de baja cadencia).
"""

from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, Field

from ..errors import SourceUnavailableError
from ..pe._common import Citation, Source
from ..registry import ToolRegistry


class LegalizeQueryInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    semantic: bool = True
    limit: int = Field(10, ge=1, le=50)
    country: str = "cl"


class LegalizeQueryOutput(BaseModel):
    results: list[Citation]
    total: int


# ---------------------------------------------------------------------------
# Dataset fallback (10 normas chilenas de referencia para Modo Preview)
# ---------------------------------------------------------------------------
_FALLBACK_LAWS: tuple[dict[str, Any], ...] = (
    {
        "law_id": "constitucion-politica-cl",
        "title": "Constitución Política de la República de Chile",
        "summary": (
            "Carta fundamental de Chile. Define derechos, garantías "
            "constitucionales, organización del Estado y Poder Judicial."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=242302",
        "year": 1980,
        "materias": ["constitucional", "derechos fundamentales"],
    },
    {
        "law_id": "ley-20730-lobby",
        "title": (
            "Ley 20.730 — Regula el lobby y las gestiones que representen "
            "intereses particulares ante autoridades y funcionarios"
        ),
        "summary": (
            "Establece el registro público de lobbistas y la obligación de "
            "autoridades de informar audiencias, donativos y viajes."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=1060115",
        "year": 2014,
        "materias": ["transparencia", "lobby", "anticorrupción"],
    },
    {
        "law_id": "ley-20285-transparencia",
        "title": "Ley 20.285 — Sobre acceso a la información pública",
        "summary": (
            "Regula el principio de transparencia activa y pasiva de la "
            "función pública, crea el Consejo para la Transparencia."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=276363",
        "year": 2008,
        "materias": ["transparencia", "acceso a la información"],
    },
    {
        "law_id": "ley-19886-compras-publicas",
        "title": (
            "Ley 19.886 — De bases sobre contratos administrativos de "
            "suministro y prestación de servicios"
        ),
        "summary": (
            "Marco normativo de compras públicas en Chile. Crea ChileCompra "
            "y el Tribunal de Contratación Pública."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=213004",
        "year": 2003,
        "materias": ["compras públicas", "contratos", "ChileCompra"],
    },
    {
        "law_id": "ley-20880-conflicto-intereses",
        "title": (
            "Ley 20.880 — Sobre probidad en la función pública y prevención "
            "de los conflictos de intereses"
        ),
        "summary": (
            "Obliga a autoridades a presentar declaración de patrimonio e "
            "intereses, define inhabilidades y régimen de fideicomiso ciego."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=1086062",
        "year": 2016,
        "materias": ["probidad", "patrimonio", "conflicto de intereses"],
    },
    {
        "law_id": "ley-19884-financiamiento-politico",
        "title": "Ley 19.884 — Sobre transparencia, límite y control del gasto electoral",
        "summary": (
            "Regula los aportes a campañas electorales, los topes de gasto "
            "y la rendición de cuentas ante el SERVEL."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=213283",
        "year": 2003,
        "materias": ["financiamiento político", "campañas", "SERVEL"],
    },
    {
        "law_id": "ley-21121-anticorrupcion",
        "title": (
            "Ley 21.121 — Modifica el Código Penal en lo relativo a delitos "
            "de cohecho y soborno"
        ),
        "summary": (
            "Aumenta penas y amplía el tipo penal de cohecho, soborno y "
            "negociación incompatible para funcionarios públicos."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=1125435",
        "year": 2018,
        "materias": ["cohecho", "soborno", "anticorrupción", "código penal"],
    },
    {
        "law_id": "ley-20393-rpe",
        "title": (
            "Ley 20.393 — Establece la responsabilidad penal de las personas "
            "jurídicas en los delitos de lavado de activos, financiamiento "
            "del terrorismo y cohecho"
        ),
        "summary": (
            "Permite imputar penalmente a empresas por cohecho a "
            "funcionarios y exige modelos de prevención de delitos."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=1008668",
        "year": 2009,
        "materias": ["personas jurídicas", "compliance", "lavado de activos"],
    },
    {
        "law_id": "ley-21595-delitos-economicos",
        "title": "Ley 21.595 — Sobre delitos económicos y atentados contra el medio ambiente",
        "summary": (
            "Sistema unificado de delitos económicos: fraude al Fisco, "
            "negociación incompatible, fraude tributario y ambientales."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=1194109",
        "year": 2023,
        "materias": ["delitos económicos", "medio ambiente", "compliance"],
    },
    {
        "law_id": "ley-20205-denuncia",
        "title": (
            "Ley 20.205 — Protege al funcionario que denuncia "
            "irregularidades y faltas al principio de probidad"
        ),
        "summary": (
            "Protección a denunciantes (whistleblowers) en la administración "
            "pública chilena."
        ),
        "url": "https://www.bcn.cl/leychile/navegar?idNorma=263962",
        "year": 2007,
        "materias": ["whistleblower", "denuncia", "probidad"],
    },
)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
async def _fetch_pool() -> Any:
    dsn = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        return None
    import asyncpg  # noqa: PLC0415

    return await asyncpg.create_pool(dsn, min_size=1, max_size=2)


async def _embed(text: str) -> list[float] | None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    import httpx  # noqa: PLC0415

    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "openai/text-embedding-3-small", "input": text},
        )
    if r.status_code != 200:
        return None
    data = r.json()
    try:
        return data["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError):
        return None


async def _semantic_search(pool: Any, embedding: list[float], limit: int) -> list[Any]:
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT id, name, metadata, embedding <=> $1::vector AS distance
            FROM entities
            WHERE country = 'cl'
              AND type = 'law'
              AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            embedding,
            limit,
        )


async def _fulltext_search(pool: Any, query: str, limit: int) -> list[Any]:
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT id, name, metadata,
                   ts_rank(search_vector, plainto_tsquery('spanish', $1)) AS distance
            FROM entities
            WHERE country = 'cl'
              AND type = 'law'
              AND search_vector @@ plainto_tsquery('spanish', $1)
            ORDER BY ts_rank(search_vector, plainto_tsquery('spanish', $1)) DESC
            LIMIT $2
            """,
            query,
            limit,
        )


def _row_to_citation(row: Any) -> Citation:
    metadata = row["metadata"] or {}
    if isinstance(metadata, str):
        import json  # noqa: PLC0415

        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    url = metadata.get("url") or metadata.get("source_url") or "internal://legalize-cl"
    title = metadata.get("title") or row["name"]
    snippet = metadata.get("summary") or metadata.get("snippet") or row["name"]
    return Citation(
        text=str(snippet)[:500],
        source=Source(url=url, source_type="legalize", title=title),
        extra={
            "entity_id": str(row["id"]),
            "score": float(row.get("distance", 0.0)),
            "country": "cl",
        },
    )


# ---------------------------------------------------------------------------
# Fallback search (cuando la DB no tiene corpus cl)
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> set[str]:
    return {w.casefold() for w in _WORD_RE.findall(text)}


def _fallback_search(query: str, limit: int) -> list[Citation]:
    """Búsqueda por tokens compartidos (overlap), suficiente para preview."""
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
        # Sin overlap: devolver top N por orden estable como sugerencias.
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
                    "country": "cl",
                    "year": law.get("year"),
                    "materias": law.get("materias", []),
                    "source": "fallback-dataset",
                },
            )
        )
    return out


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------
@ToolRegistry.register(
    country="cl",
    input_model=LegalizeQueryInput,
    output_model=LegalizeQueryOutput,
    cache_ttl=7 * 24 * 3600,
    tags=("legal", "corpus", "preview"),
)
async def query_legalize_cl(payload: LegalizeQueryInput) -> LegalizeQueryOutput:
    """Búsqueda en corpus legalize-cl (Ley Chile / BCN).

    Si la DB tiene leyes ingestadas (country='cl'), corre semantic search
    con pgvector. Si no, fallback a dataset hardcoded de 10 normas (Modo
    Preview S-18).
    """
    pool = await _fetch_pool()
    rows: list[Any] = []
    if pool is not None:
        try:
            if payload.semantic:
                embedding = await _embed(payload.query)
                if embedding is not None:
                    rows = await _semantic_search(pool, embedding, payload.limit)
                else:
                    rows = await _fulltext_search(pool, payload.query, payload.limit)
            else:
                rows = await _fulltext_search(pool, payload.query, payload.limit)
        except Exception as exc:
            await pool.close()
            raise SourceUnavailableError(
                f"legalize-cl query failed: {exc}",
                tool="query_legalize_cl",
                country="cl",
                cause=exc,
            ) from exc
        finally:
            if pool is not None:
                await pool.close()

    if rows:
        citations = [_row_to_citation(r) for r in rows]
        return LegalizeQueryOutput(results=citations, total=len(citations))

    citations = _fallback_search(payload.query, payload.limit)
    return LegalizeQueryOutput(results=citations, total=len(citations))


__all__ = ["query_legalize_cl", "LegalizeQueryInput", "LegalizeQueryOutput"]
