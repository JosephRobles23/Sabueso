from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Request, Response, status

from src.db.pool import healthcheck

log = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe — never touches the DB. Cloud Run uses this to decide if a container is up."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request, response: Response) -> dict[str, Any]:
    """Readiness probe — fails 503 if the DB is unreachable. Cloud Run gates traffic on this."""
    pool = getattr(request.app.state, "db_pool", None)
    db_status = "ok"
    if pool is None:
        db_status = "fail"
    else:
        try:
            if not await healthcheck(pool):
                db_status = "fail"
        except Exception as exc:
            log.warning("readyz.db_failed", error=str(exc))
            db_status = "fail"

    body: dict[str, Any] = {"db": db_status, "supabase": db_status}
    if db_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return body
