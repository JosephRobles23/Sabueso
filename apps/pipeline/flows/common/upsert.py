"""Upserts idempotentes a Supabase (entities, sources, claims, edges).

Convención: cada upsert devuelve el id (UUID) del row resultante. Los flows
no deben construir IDs; siempre delegan en estos helpers.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import asyncpg

from .db import conn


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class EntityUpsert:
    country: str
    type: str
    identifier: str | None
    name: str
    aliases: list[str] | None = None
    metadata: dict[str, Any] | None = None
    embedding: list[float] | None = None


def _vector_literal(values: Sequence[float]) -> str:
    """asyncpg no convierte list[float] -> vector directamente; pasamos texto."""
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


async def upsert_entity(
    e: EntityUpsert, *, connection: asyncpg.Connection | None = None
) -> uuid.UUID:
    """UNIQUE(country, type, identifier) → idempotente.

    Si identifier es None usamos un identifier sintético derivado del name
    para mantener la unicidad. Esto importa para 'law' donde el identifier
    es el code de la norma.
    """
    aliases = e.aliases or []
    metadata = e.metadata or {}
    identifier = e.identifier or hashlib.sha256(e.name.encode("utf-8")).hexdigest()[:32]

    embedding_lit = _vector_literal(e.embedding) if e.embedding else None

    sql = """
        INSERT INTO entities (country, type, identifier, name, aliases, metadata, embedding)
        VALUES ($1, $2, $3, $4, $5::text[], $6::jsonb, $7::vector)
        ON CONFLICT (country, type, identifier) DO UPDATE
        SET name = EXCLUDED.name,
            aliases = EXCLUDED.aliases,
            metadata = entities.metadata || EXCLUDED.metadata,
            embedding = COALESCE(EXCLUDED.embedding, entities.embedding),
            updated_at = now()
        RETURNING id
    """
    args = (
        e.country,
        e.type,
        identifier,
        e.name,
        aliases,
        json.dumps(metadata),
        embedding_lit,
    )

    if connection is not None:
        row = await connection.fetchrow(sql, *args)
    else:
        async with conn() as c:
            row = await c.fetchrow(sql, *args)
    return row["id"]


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class SourceUpsert:
    url: str
    source_type: str  # 'legalize'|'seace'|'jne'|...
    title: str | None = None
    content_hash: str | None = None
    content_storage: str | None = None  # gs://...
    country: str | None = None


async def upsert_source(
    s: SourceUpsert, *, connection: asyncpg.Connection | None = None
) -> uuid.UUID:
    """UNIQUE(url, snapshot_at) → cada corrida crea un nuevo snapshot.

    Para mantener idempotencia razonable (no insertar uno nuevo cada vez si
    el contenido no cambió), buscamos primero un source previo con mismo
    content_hash y devolvemos su id si existe.
    """
    sql_lookup = """
        SELECT id FROM sources
        WHERE url=$1 AND content_hash IS NOT DISTINCT FROM $2
        ORDER BY snapshot_at DESC LIMIT 1
    """
    sql_insert = """
        INSERT INTO sources (url, source_type, title, content_hash, content_storage, country)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
    """

    async def _run(c: asyncpg.Connection) -> uuid.UUID:
        existing = await c.fetchrow(sql_lookup, s.url, s.content_hash)
        if existing is not None:
            return existing["id"]
        row = await c.fetchrow(
            sql_insert,
            s.url,
            s.source_type,
            s.title,
            s.content_hash,
            s.content_storage,
            s.country,
        )
        return row["id"]

    if connection is not None:
        return await _run(connection)
    async with conn() as c:
        return await _run(c)


# ---------------------------------------------------------------------------
# Claims & Edges (sin investigation — pipeline-level claims)
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ClaimUpsert:
    entity_id: uuid.UUID
    predicate: str
    object_value: Any
    source_id: uuid.UUID
    source_extract: str | None = None
    source_hash: str | None = None
    confidence: float = 0.95
    agent_callsign: str = "sabueso-pipeline"
    object_entity_id: uuid.UUID | None = None


async def insert_claim(
    c: ClaimUpsert, *, connection: asyncpg.Connection | None = None
) -> uuid.UUID:
    """Inserta claim sin investigation_id (pipeline-level).

    Idempotencia: (entity_id, predicate, source_id) — si ya existe el mismo
    claim del mismo source, devolvemos el existente. No es un UNIQUE formal en
    la tabla, así que lo verificamos antes.
    """
    sql_lookup = """
        SELECT id FROM claims
        WHERE entity_id=$1 AND predicate=$2 AND source_id=$3
          AND superseded_by IS NULL
        LIMIT 1
    """
    sql_insert = """
        INSERT INTO claims (
            entity_id, predicate, object_value, object_entity_id,
            source_id, source_extract, source_hash, confidence, agent_callsign
        )
        VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, $8, $9)
        RETURNING id
    """
    extract = c.source_extract
    if extract and len(extract) > 500:
        extract = extract[:497] + "..."
    args = (
        c.entity_id,
        c.predicate,
        json.dumps(c.object_value, default=str),
        c.object_entity_id,
        c.source_id,
        extract,
        c.source_hash,
        c.confidence,
        c.agent_callsign,
    )

    async def _run(cn: asyncpg.Connection) -> uuid.UUID:
        existing = await cn.fetchrow(sql_lookup, c.entity_id, c.predicate, c.source_id)
        if existing is not None:
            return existing["id"]
        row = await cn.fetchrow(sql_insert, *args)
        return row["id"]

    if connection is not None:
        return await _run(connection)
    async with conn() as cn:
        return await _run(cn)


@dataclass(slots=True)
class EdgeUpsert:
    from_entity: uuid.UUID
    to_entity: uuid.UUID
    type: str
    weight: float = 1.0
    confidence: float = 0.9
    evidence_claims: list[uuid.UUID] | None = None
    agent_callsign: str = "sabueso-pipeline"


async def upsert_edge(e: EdgeUpsert, *, connection: asyncpg.Connection | None = None) -> uuid.UUID:
    """UNIQUE(from_entity, to_entity, type) → idempotente."""
    evidence = e.evidence_claims or []
    sql = """
        INSERT INTO edges (
            from_entity, to_entity, type, weight, confidence, evidence_claims, agent_callsign
        )
        VALUES ($1, $2, $3, $4, $5, $6::uuid[], $7)
        ON CONFLICT (from_entity, to_entity, type) DO UPDATE
        SET weight = EXCLUDED.weight,
            confidence = GREATEST(edges.confidence, EXCLUDED.confidence),
            evidence_claims = ARRAY(
                SELECT DISTINCT unnest(edges.evidence_claims || EXCLUDED.evidence_claims)
            )
        RETURNING id
    """
    args = (
        e.from_entity,
        e.to_entity,
        e.type,
        e.weight,
        e.confidence,
        evidence,
        e.agent_callsign,
    )
    if connection is not None:
        row = await connection.fetchrow(sql, *args)
    else:
        async with conn() as c:
            row = await c.fetchrow(sql, *args)
    return row["id"]
