from __future__ import annotations

import time

from src.db.repository.entities import EntityRepo
from src.models.entity import Country
from src.models.search import SearchHit, SearchResponse


class SearchService:
    def __init__(self, entities: EntityRepo) -> None:
        self._entities = entities

    async def search(
        self,
        query: str,
        country: Country | None,
        limit: int,
    ) -> SearchResponse:
        started = time.perf_counter()
        rows = await self._entities.search(query=query, country=country, limit=limit)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        hits = [
            SearchHit(
                id=row["id"],
                country=row["country"],
                type=row["type"],
                name=row["name"],
                identifier=row.get("identifier"),
                score=float(row.get("score") or 0.0),
            )
            for row in rows
        ]
        return SearchResponse(query=query, country=country, took_ms=elapsed_ms, results=hits)
