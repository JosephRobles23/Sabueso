from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.auth.current_user import CurrentUser, get_current_user
from src.deps import InvestigationServiceDep
from src.models.investigation import InvestigationCreate, InvestigationCreated
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
