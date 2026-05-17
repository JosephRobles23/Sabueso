"""find_relatives.

Consulta el grafo en Supabase (``edges`` con type IN family_*) para devolver
familiares hasta N grados de un DNI. La pre-población viene de la pipeline de
ingestión (S-15) que matcheó RENIEC/JNE.

TTL: 30 días.
"""

from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..errors import SourceUnavailableError
from ..registry import ToolRegistry
from ._common import Citation, Source

DNI_RE = re.compile(r"^\d{8}$")
FAMILY_EDGE_TYPES = (
    "spouse_of",
    "parent_of",
    "child_of",
    "sibling_of",
    "relative_of",
)


class RelativesInput(BaseModel):
    dni: str = Field(..., description="DNI raíz desde donde expandir.")
    degree: int = Field(2, ge=1, le=3, description="Grados de cercanía (BFS).")

    @field_validator("dni")
    @classmethod
    def _dni(cls, v: str) -> str:
        v = v.strip()
        if not DNI_RE.match(v):
            raise ValueError("DNI debe tener 8 dígitos numéricos.")
        return v


class Relative(BaseModel):
    dni: str | None = None
    name: str
    relation: str  # "spouse", "parent", "sibling-of-sibling", etc.
    degree: int


class RelativesOutput(BaseModel):
    root_dni: str
    relatives: list[Relative]
    citations: list[Citation]


@ToolRegistry.register(
    country="pe",
    input_model=RelativesInput,
    output_model=RelativesOutput,
    cache_ttl=30 * 24 * 3600,
    tags=("graph", "family"),
)
async def find_relatives(payload: RelativesInput) -> RelativesOutput:
    """BFS sobre ``edges`` family_* en Supabase hasta el grado indicado."""
    pool = await _fetch_pool()
    if pool is None:
        return RelativesOutput(root_dni=payload.dni, relatives=[], citations=[])

    try:
        root_id = await _entity_id_for_dni(pool, payload.dni)
        if root_id is None:
            return RelativesOutput(
                root_dni=payload.dni,
                relatives=[],
                citations=[
                    Citation(
                        text=f"DNI {payload.dni} no encontrado en grafo de entidades.",
                        source=Source(url="internal://entities", source_type="press"),
                    )
                ],
            )
        rows = await _bfs(pool, root_id, payload.degree)
    except Exception as exc:
        raise SourceUnavailableError(
            f"relatives lookup failed: {exc}",
            tool="find_relatives",
            country="pe",
            cause=exc,
        ) from exc
    finally:
        await pool.close()

    relatives = [
        Relative(
            dni=r["identifier"],
            name=r["name"],
            relation=r["edge_type"],
            degree=int(r["depth"]),
        )
        for r in rows
    ]
    citations = [
        Citation(
            text=f"{rel.name} ({rel.relation}, grado {rel.degree})",
            source=Source(url="internal://entities", source_type="press"),
        )
        for rel in relatives
    ]
    return RelativesOutput(root_dni=payload.dni, relatives=relatives, citations=citations)


async def _fetch_pool() -> Any:
    dsn = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        return None
    import asyncpg  # noqa: PLC0415

    return await asyncpg.create_pool(dsn, min_size=1, max_size=2)


async def _entity_id_for_dni(pool: Any, dni: str) -> str | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM entities WHERE country='pe' AND type='person' AND identifier=$1",
            dni,
        )
    return str(row["id"]) if row else None


async def _bfs(pool: Any, root_id: str, max_depth: int) -> list[Any]:
    """BFS recursivo en SQL. Usa CTE WITH RECURSIVE."""
    edge_types = list(FAMILY_EDGE_TYPES)
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            WITH RECURSIVE walk AS (
                SELECT e.to_entity   AS node_id,
                       e.type        AS edge_type,
                       1             AS depth
                FROM edges e
                WHERE e.from_entity = $1::uuid
                  AND e.type = ANY($2::text[])
                UNION ALL
                SELECT e.to_entity, e.type, w.depth + 1
                FROM edges e
                JOIN walk w ON e.from_entity = w.node_id
                WHERE w.depth < $3
                  AND e.type = ANY($2::text[])
            )
            SELECT DISTINCT ent.id, ent.name, ent.identifier, w.edge_type, MIN(w.depth) AS depth
            FROM walk w
            JOIN entities ent ON ent.id = w.node_id
            GROUP BY ent.id, ent.name, ent.identifier, w.edge_type
            ORDER BY depth ASC, ent.name ASC
            """,
            root_id,
            edge_types,
            max_depth,
        )


__all__ = ["find_relatives", "RelativesInput", "RelativesOutput", "Relative"]
