from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.entity import Country, EntityType


class SearchHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    country: Country
    type: EntityType
    name: str
    identifier: str | None = None
    score: float = Field(ge=0.0)


class SearchResponse(BaseModel):
    query: str
    country: Country | None = None
    took_ms: int
    results: list[SearchHit]
