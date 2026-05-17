from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app
from src.settings import Settings


class FakePool:
    """In-memory stand-in for asyncpg.Pool used by every repo test.

    We don't try to be a SQL engine — we recognize the queries by substring and return
    canned rows. That's enough to exercise every code path in the API layer without
    spinning up Postgres.
    """

    def __init__(self) -> None:
        self.entities: dict[UUID, dict[str, Any]] = {}
        self.investigations: dict[UUID, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.claims_by_entity: dict[UUID, list[dict[str, Any]]] = {}
        self.enqueued: list[dict[str, Any]] = []
        self.fail_healthcheck = False
        self.search_results: list[dict[str, Any]] = []

    # asyncpg API surface ---------------------------------------------------

    async def fetchval(self, query: str, *args: Any) -> Any:
        q = _normalize(query)
        if "select 1" in q:
            if self.fail_healthcheck:
                raise RuntimeError("simulated db failure")
            return 1
        if "insert into investigations" in q:
            new_id = uuid4()
            target_entity_id, country, locale, user_id = args
            self.investigations[new_id] = {
                "id": new_id,
                "target_entity_id": target_entity_id,
                "country": country,
                "locale": locale,
                "user_id": user_id,
                "status": "pending",
            }
            return new_id
        raise AssertionError(f"unexpected fetchval: {query!r}")

    async def fetchrow(self, query: str, *args: Any) -> Any:
        q = _normalize(query)
        if "from entities" in q and "lower(name) = lower" in q:
            country, entity_type, name = args
            for entity in self.entities.values():
                if (
                    entity["country"] == country
                    and entity["type"] == entity_type
                    and entity["name"].lower() == name.lower()
                ):
                    return entity
            return None
        if "insert into entities" in q:
            country, entity_type, name = args
            new_id = uuid4()
            row = {
                "id": new_id,
                "country": country,
                "type": entity_type,
                "identifier": None,
                "name": name,
                "aliases": [],
                "metadata": {},
                "created_at": None,
                "updated_at": None,
            }
            self.entities[new_id] = row
            return row
        if "from entities" in q and "where id =" in q:
            (entity_id,) = args
            return self.entities.get(entity_id)
        if "from investigations" in q:
            (investigation_id,) = args
            return self.investigations.get(investigation_id)
        raise AssertionError(f"unexpected fetchrow: {query!r}")

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        q = _normalize(query)
        if "from entities" in q and "similarity" in q:
            return list(self.search_results)
        if "from claims" in q:
            entity_id, _limit = args
            return list(self.claims_by_entity.get(entity_id, []))
        if "from investigation_events" in q:
            inv_id, last_id, _limit = args
            return [
                e for e in self.events
                if e["investigation_id"] == inv_id and e["id"] > last_id
            ]
        raise AssertionError(f"unexpected fetch: {query!r}")

    async def execute(self, query: str, *args: Any) -> str:
        q = _normalize(query)
        if "pgmq.send" in q:
            queue, payload = args
            self.enqueued.append({"queue": queue, "payload": payload})
            return "SELECT 1"
        raise AssertionError(f"unexpected execute: {query!r}")

    async def close(self) -> None:
        return None


def _normalize(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip().lower()


@pytest.fixture
def fake_pool() -> FakePool:
    return FakePool()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        supabase_db_url="postgresql://test",
        supabase_jwks_url="",  # JWKS disabled → anonymous-friendly
        pgmq_queue="investigation_queue",
        cors_origins=["http://localhost:3000"],
        log_level="WARNING",
    )


@pytest.fixture
async def client(settings: Settings, fake_pool: FakePool) -> AsyncIterator[AsyncClient]:
    """ASGI client that skips the real lifespan: we inject our FakePool directly."""
    app = create_app(settings)
    # Bypass lifespan: ASGITransport with lifespan="off" never runs our startup.
    app.state.db_pool = fake_pool
    app.state.settings = settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def seed_entity(fake_pool: FakePool) -> dict[str, Any]:
    eid = uuid4()
    row = {
        "id": eid,
        "country": "pe",
        "type": "person",
        "identifier": "12345678",
        "name": "Vladimir Cerrón",
        "aliases": ["VC"],
        "metadata": {},
        "created_at": None,
        "updated_at": None,
    }
    fake_pool.entities[eid] = row
    return row


@pytest.fixture(autouse=True)
def _isolate_settings_cache() -> Iterator[None]:
    """Clear the get_settings lru_cache between tests so env tweaks take effect."""
    from src.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
