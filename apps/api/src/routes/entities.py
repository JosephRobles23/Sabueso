from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.deps import ClaimRepoDep, EntityRepoDep
from src.models.entity import Entity

router = APIRouter(tags=["entities"])


@router.get("/entities/{entity_id}", response_model=Entity)
async def get_entity(entity_id: UUID, entities: EntityRepoDep) -> Entity:
    entity = await entities.get(entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="entity not found")
    return entity


@router.get("/entities/{entity_id}/claims")
async def list_claims(entity_id: UUID, claims: ClaimRepoDep) -> dict[str, Any]:
    rows = await claims.list_for_entity(entity_id)
    return {"entity_id": str(entity_id), "claims": rows}
