from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from src.db.pool import PoolLike
from src.db.repository.claims import ClaimRepo
from src.db.repository.entities import EntityRepo
from src.db.repository.events import EventRepo
from src.db.repository.investigations import InvestigationRepo
from src.services.investigation import InvestigationService
from src.services.search import SearchService
from src.settings import Settings, get_settings


def get_pool(request: Request) -> PoolLike:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise RuntimeError("db pool not initialized — did lifespan run?")
    return pool  # type: ignore[no-any-return]


def get_app_settings() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
PoolDep = Annotated[PoolLike, Depends(get_pool)]


def get_investigation_repo(pool: PoolDep) -> InvestigationRepo:
    return InvestigationRepo(pool)


def get_entity_repo(pool: PoolDep) -> EntityRepo:
    return EntityRepo(pool)


def get_claim_repo(pool: PoolDep) -> ClaimRepo:
    return ClaimRepo(pool)


def get_event_repo(pool: PoolDep) -> EventRepo:
    return EventRepo(pool)


def get_investigation_service(
    settings: SettingsDep,
    investigations: Annotated[InvestigationRepo, Depends(get_investigation_repo)],
    entities: Annotated[EntityRepo, Depends(get_entity_repo)],
) -> InvestigationService:
    return InvestigationService(
        investigations=investigations,
        entities=entities,
        queue_name=settings.pgmq_queue,
    )


def get_search_service(
    entities: Annotated[EntityRepo, Depends(get_entity_repo)],
) -> SearchService:
    return SearchService(entities)


InvestigationServiceDep = Annotated[InvestigationService, Depends(get_investigation_service)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
EntityRepoDep = Annotated[EntityRepo, Depends(get_entity_repo)]
ClaimRepoDep = Annotated[ClaimRepo, Depends(get_claim_repo)]
