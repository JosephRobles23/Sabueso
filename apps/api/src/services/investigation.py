from __future__ import annotations

from uuid import UUID

import structlog

from src.db.repository.entities import EntityRepo
from src.db.repository.investigations import InvestigationRepo
from src.models.investigation import InvestigationCreate, InvestigationCreated

log = structlog.get_logger(__name__)


class InvestigationService:
    def __init__(
        self,
        *,
        investigations: InvestigationRepo,
        entities: EntityRepo,
        queue_name: str,
    ) -> None:
        self._investigations = investigations
        self._entities = entities
        self._queue = queue_name

    async def create_and_dispatch(
        self,
        payload: InvestigationCreate,
        user_id: UUID | None,
    ) -> InvestigationCreated:
        """Resolve entity, INSERT investigation, push to pgmq. <500ms p95 target.

        Worker dispatch (gcloud run jobs execute) is intentionally out of scope here —
        S-07 wires the worker; the queue insert is what triggers it.
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
            # The row is already persisted; surface the failure but don't lose the id.
            log.error(
                "investigation.enqueue_failed",
                investigation_id=str(investigation_id),
                error=str(exc),
            )
            raise

        return InvestigationCreated(
            investigation_id=investigation_id,
            entity_id=entity.id,
            status="pending",
        )
