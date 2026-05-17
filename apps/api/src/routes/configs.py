from __future__ import annotations

from typing import Annotated, get_args

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.current_user import CurrentUser, require_user
from src.db.repository.investigator_configs import InvestigatorConfigRepo
from src.deps import ConfigRepoDep
from src.models.investigator_config import (
    ConfigPatch,
    InvestigatorCallsign,
    InvestigatorConfig,
    InvestigatorConfigList,
)

router = APIRouter(tags=["configs"])

_VALID_CALLSIGNS = frozenset(get_args(InvestigatorCallsign))


@router.get("/configs", response_model=InvestigatorConfigList)
async def list_configs(
    repo: ConfigRepoDep,
    user: Annotated[CurrentUser, Depends(require_user)],
) -> InvestigatorConfigList:
    """Listado de configs del usuario autenticado. Filtra siempre por user_id
    (defense-in-depth: RLS ya bloquea cross-tenant si pasara service_role)."""
    configs = await repo.list_for_user(user.id)
    return InvestigatorConfigList(configs=configs)


@router.patch("/configs/{callsign}", response_model=InvestigatorConfig)
async def patch_config(
    callsign: str,
    patch: ConfigPatch,
    repo: ConfigRepoDep,
    user: Annotated[CurrentUser, Depends(require_user)],
) -> InvestigatorConfig:
    """Shallow merge JSONB sobre la config del callsign. Idempotente."""
    if callsign not in _VALID_CALLSIGNS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"unknown callsign: {callsign}",
        )
    updated = await repo.patch(user.id, callsign, patch.config)
    if updated is None:
        # El UPSERT del repo siempre devuelve fila; un None acá implicaría que
        # asyncpg perdió el RETURNING o que la DB rechazó el INSERT por FK.
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to upsert config",
        )
    return updated


__all__ = ["router", "InvestigatorConfigRepo"]
