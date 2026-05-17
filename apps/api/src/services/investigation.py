from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
import structlog

from src.db.repository.entities import EntityRepo
from src.db.repository.investigations import InvestigationRepo
from src.models.investigation import InvestigationCreate, InvestigationCreated

log = structlog.get_logger(__name__)

# Cloud Run Admin API base. ID tokens minted for this audience are accepted
# by the v2 jobs:run endpoint when the caller has roles/run.invoker on the job.
_RUN_API_AUDIENCE = "https://run.googleapis.com"
_RUN_API_BASE = "https://run.googleapis.com/v2"


class InvestigationService:
    def __init__(
        self,
        *,
        investigations: InvestigationRepo,
        entities: EntityRepo,
        queue_name: str,
        dispatch_enabled: bool = False,
        gcp_project_id: str = "",
        gcp_region: str = "",
        worker_job_name: str = "",
        dispatch_timeout_seconds: float = 15.0,
    ) -> None:
        self._investigations = investigations
        self._entities = entities
        self._queue = queue_name
        self._dispatch_enabled = dispatch_enabled
        self._project = gcp_project_id
        self._region = gcp_region
        self._job_name = worker_job_name
        self._dispatch_timeout = dispatch_timeout_seconds

    async def create_and_dispatch(
        self,
        payload: InvestigationCreate,
        user_id: UUID | None,
    ) -> InvestigationCreated:
        """Resolve entity, INSERT investigation, push to pgmq, kick the worker.

        Worker dispatch is gated by the ``dispatch_worker`` setting so the
        S-07 path can be smoke-tested independently of S-06's orchestrator.
        """
        entity = await self._entities.find_or_create_stub(
            name=payload.entity_query,
            country=payload.country,
        )

        investigation_id = await self._investigations.create(
            target_entity_id=entity.id,
            country=payload.country,
            locale=payload.locale,
            user_id=user_id,
        )

        try:
            await self._investigations.enqueue(investigation_id, self._queue)
        except Exception as exc:
            log.error(
                "investigation.enqueue_failed",
                investigation_id=str(investigation_id),
                error=str(exc),
            )
            raise

        if self._dispatch_enabled:
            try:
                await self.dispatch_worker(investigation_id)
            except Exception as exc:
                # The row is in pgmq; a backfill consumer can still pick it up.
                # Surface the dispatch failure but don't fail the request.
                log.error(
                    "investigation.dispatch_failed",
                    investigation_id=str(investigation_id),
                    error=str(exc),
                )

        return InvestigationCreated(
            investigation_id=investigation_id,
            entity_id=entity.id,
            status="pending",
        )

    async def dispatch_worker(self, investigation_id: UUID) -> None:
        """Trigger a Cloud Run Job execution for ``investigation_id``.

        Uses google-auth to mint an OIDC ID token with audience
        ``https://run.googleapis.com`` and POSTs to the v2 ``:run`` endpoint
        with a container env override carrying the investigation id.

        Service-account requirement: the runtime SA needs roles/run.invoker
        on the ``investigation-worker`` job.
        """
        if not (self._project and self._region and self._job_name):
            raise RuntimeError(
                "dispatch_worker called without gcp_project_id / gcp_region / "
                "worker_job_name configured"
            )

        token = await asyncio.to_thread(self._fetch_id_token)

        url = (
            f"{_RUN_API_BASE}/projects/{self._project}"
            f"/locations/{self._region}/jobs/{self._job_name}:run"
        )
        body = {
            "overrides": {
                "containerOverrides": [
                    {
                        "env": [
                            {
                                "name": "INVESTIGATION_ID",
                                "value": str(investigation_id),
                            }
                        ]
                    }
                ]
            }
        }

        async with httpx.AsyncClient(timeout=self._dispatch_timeout) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()

        log.info(
            "investigation.dispatched",
            investigation_id=str(investigation_id),
            job=self._job_name,
            status=resp.status_code,
        )

    @staticmethod
    def _fetch_id_token() -> str:
        """Return an OIDC ID token for the Cloud Run Admin API audience.

        Lazy import — google-auth lives in the optional ``gcp`` extra so the
        base image doesn't pay for it until dispatch is actually enabled.
        """
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        request = Request()
        # fetch_id_token resolves the right IDTokenCredentials implementation
        # (compute-engine / impersonated / service-account) from ADC and refreshes it.
        token: str = id_token.fetch_id_token(request, _RUN_API_AUDIENCE)
        return token
