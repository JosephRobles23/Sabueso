from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.current_user import CurrentUser, get_current_user
from src.db.repository.investigations import InvestigationRepo
from src.deps import InvestigationServiceDep, get_investigation_repo
from src.models.investigation import (
    Investigation,
    InvestigationCreate,
    InvestigationCreated,
)
from src.services.rate_limit import allow_request

router = APIRouter(tags=["investigations"])


@router.post(
    "/investigate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=InvestigationCreated,
)
async def create_investigation(
    payload: InvestigationCreate,
    service: InvestigationServiceDep,
    user: CurrentUser | None = Depends(get_current_user),
) -> InvestigationCreated:
    """Accept the investigation request, persist, enqueue. <500ms p95.

    Rate limit is a soft hook here (S-20 fills the real implementation).
    """
    await allow_request(user_id=user.id if user else None)
    return await service.create_and_dispatch(
        payload=payload,
        user_id=user.id if user else None,
    )


@router.get("/investigations/{investigation_id}", response_model=Investigation)
async def get_investigation(
    investigation_id: UUID,
    repo: Annotated[InvestigationRepo, Depends(get_investigation_repo)],
) -> Investigation:
    """Snapshot del estado de una investigación. Lo usa el smoke test (S-10)
    para verificar `status='complete'` después de drenar el SSE."""
    investigation = await repo.get(investigation_id)
    if investigation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="investigation not found")
    return investigation
