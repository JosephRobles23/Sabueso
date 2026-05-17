from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.auth.current_user import CurrentUser, get_current_user
from src.auth.rate_limit import enforce_rate_limit
from src.deps import InvestigationServiceDep
from src.models.investigation import InvestigationCreate, InvestigationCreated

router = APIRouter(tags=["investigations"])


@router.post(
    "/investigate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=InvestigationCreated,
    dependencies=[Depends(enforce_rate_limit)],
)
async def create_investigation(
    payload: InvestigationCreate,
    service: InvestigationServiceDep,
    user: CurrentUser | None = Depends(get_current_user),
) -> InvestigationCreated:
    """Accept the investigation request, persist, enqueue. <500ms p95.

    Rate limit is enforced by the ``enforce_rate_limit`` dependency above:
    anon → 10/IP/24h, auth → 50/user/24h. Edge middleware is the primary
    bucket; this backend check is defense-in-depth (see S-20).
    """
    return await service.create_and_dispatch(
        payload=payload,
        user_id=user.id if user else None,
    )
