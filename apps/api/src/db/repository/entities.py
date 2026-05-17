from __future__ import annotations

from typing import Any
from uuid import UUID

from src.db.pool import PoolLike
from src.models.entity import Country, Entity, EntityType


class EntityRepo:
    """Read/write entities. Schema lives in S-02; we use the same column names defined there."""

    def __init__(self, pool: PoolLike) -> None:
        self._pool = pool

    async def get(self, entity_id: UUID) -> Entity | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, country, type, identifier, name, aliases, metadata,
                   created_at, updated_at
            FROM entities
            WHERE id = $1
            """,
            entity_id,
        )
        return self._row_to_entity(row) if row else None

    async def find_or_create_stub(
        self,
        *,
        name: str,
        country: Country,
        entity_type: EntityType = "person",
    ) -> Entity:
        """Find an entity by fuzzy name match within country, or insert a stub.

        Stub creation lets /investigate return quickly without waiting for the worker to
        canonicalize the target. The worker will dedup later via (country, type, identifier).
        """
        row = await self._pool.fetchrow(
            """
            SELECT id, country, type, identifier, name, aliases, metadata,
                   created_at, updated_at
            FROM entities
            WHERE country = $1
              AND type = $2
              AND lower(name) = lower($3)
            LIMIT 1
            """,
            country,
            entity_type,
            name,
        )
        if row:
            return self._row_to_entity(row)

        new_row = await self._pool.fetchrow(
            """
            INSERT INTO entities (country, type, name)
            VALUES ($1, $2, $3)
            RETURNING id, country, type, identifier, name, aliases, metadata,
                      created_at, updated_at
            """,
            country,
            entity_type,
            name,
        )
        if new_row is None:
            raise RuntimeError("INSERT entities RETURNING returned no row")
        return self._row_to_entity(new_row)

    @staticmethod
    def _row_to_entity(row: Any) -> Entity:
        data = dict(row)
        # aliases/metadata may come back as None when columns have no default in test fixtures.
        data["aliases"] = data.get("aliases") or []
        data["metadata"] = data.get("metadata") or {}
        return Entity.model_validate(data)

    async def search(
        self,
        query: str,
        country: Country | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """pg_trgm + tsvector hybrid ranking. Returns raw dicts so the service can shape hits."""
        sql = """
            SELECT id, country, type, name, identifier,
                   GREATEST(
                       similarity(name, $1),
                       ts_rank(search_vector, plainto_tsquery('spanish', $1))
                   ) AS score
            FROM entities
            WHERE ($2::char(2) IS NULL OR country = $2)
              AND (name % $1 OR search_vector @@ plainto_tsquery('spanish', $1))
            ORDER BY score DESC
            LIMIT $3
        """
        rows = await self._pool.fetch(sql, query, country, limit)
        return [dict(r) for r in rows]
