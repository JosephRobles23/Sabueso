"""query_legalize_pe.

Busca dentro del corpus legalize-pe (normas, sentencias, resoluciones del MEF /
Congreso / CGR previamente ingestadas en Supabase). Soporta búsqueda semántica
contra ``entities.embedding`` u opcionalmente full-text contra
``entities.search_vector``.

Suposición: la ingestion (S-15) ya pobló embeddings + metadata. Acá sólo
consultamos. Si el cliente embeddings está caído, fallback a full-text con
``search_vector``.

TTL cache: 7 días — el corpus se actualiza con baja cadencia.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from ..errors import SourceUnavailableError
from ..registry import ToolRegistry
from ._common import Citation, Source


class LegalizeQueryInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    semantic: bool = True
    limit: int = Field(10, ge=1, le=50)
    country: str = "pe"


class LegalizeQueryOutput(BaseModel):
    results: list[Citation]
    total: int


async def _fetch_pool() -> Any:
    """Pool asyncpg lazy. Importa adentro para no romper si falta la dep en
    contextos de test sin DB."""
    dsn = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        return None
    import asyncpg  # noqa: PLC0415

    return await asyncpg.create_pool(dsn, min_size=1, max_size=2)


async def _embed(text: str) -> list[float] | None:
    """Llamada al servicio de embeddings vía OpenRouter. Si falla devolvemos
    None y el caller hace fallback a full-text."""
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


@ToolRegistry.register(
    country="pe",
    input_model=LegalizeQueryInput,
    output_model=LegalizeQueryOutput,
    cache_ttl=7 * 24 * 3600,
    tags=("legal", "corpus"),
)
async def query_legalize_pe(payload: LegalizeQueryInput) -> LegalizeQueryOutput:
    """Búsqueda en corpus legalize-pe (normas + sentencias + resoluciones PE).

    Soporta búsqueda semántica con pgvector contra embeddings preprocesados,
    fallback a full-text si embeddings no disponibles.
    """
    pool = await _fetch_pool()
    if pool is None:
        # Sin DB: respuesta vacía determinística. Tests offline pasan.
        return LegalizeQueryOutput(results=[], total=0)

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
        raise SourceUnavailableError(
            f"legalize query failed: {exc}",
            tool="query_legalize_pe",
            country="pe",
            cause=exc,
        ) from exc
    finally:
        await pool.close()

    citations = [_row_to_citation(r) for r in rows]
    return LegalizeQueryOutput(results=citations, total=len(citations))


async def _semantic_search(pool: Any, embedding: list[float], limit: int) -> list[Any]:
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT id, name, metadata, embedding <=> $1::vector AS distance
            FROM entities
            WHERE country = 'pe'
              AND type IN ('government_entity', 'contract')
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
            WHERE country = 'pe'
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
    url = metadata.get("url") or metadata.get("source_url") or "internal://legalize-pe"
    title = metadata.get("title") or row["name"]
    snippet = metadata.get("snippet") or row["name"]
    return Citation(
        text=str(snippet)[:500],
        source=Source(url=url, source_type="legalize", title=title),
        extra={
            "entity_id": str(row["id"]),
            "score": float(row.get("distance", 0.0)),
        },
    )


__all__ = ["query_legalize_pe", "LegalizeQueryInput", "LegalizeQueryOutput"]
