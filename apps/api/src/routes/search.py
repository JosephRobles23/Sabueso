from __future__ import annotations

from fastapi import APIRouter, Query

from src.deps import SearchServiceDep
from src.models.entity import Country
from src.models.search import SearchResponse

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    service: SearchServiceDep,
    q: str = Query(min_length=2, max_length=120, description="Search query"),
    country: Country | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
) -> SearchResponse:
    """Autocomplete + name search. pg_trgm + tsvector hybrid, <100ms p95."""
    return await service.search(query=q, country=country, limit=limit)
