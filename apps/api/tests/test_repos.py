from __future__ import annotations

from uuid import uuid4

import pytest

from src.db.repository.entities import EntityRepo
from src.db.repository.events import EventRepo
from src.db.repository.investigations import InvestigationRepo
from src.models.investigation import Investigation
from tests.conftest import FakePool


@pytest.mark.asyncio
async def test_entity_repo_find_or_create_stub_idempotent(fake_pool: FakePool) -> None:
    repo = EntityRepo(fake_pool)
    a = await repo.find_or_create_stub(name="Ana López", country="pe")
    b = await repo.find_or_create_stub(name="ANA LÓPEZ", country="pe")
    assert a.id == b.id  # case-insensitive match within country


@pytest.mark.asyncio
async def test_entity_repo_get_returns_none_for_missing(fake_pool: FakePool) -> None:
    repo = EntityRepo(fake_pool)
    assert await repo.get(uuid4()) is None


@pytest.mark.asyncio
async def test_investigation_repo_create_and_fetch(fake_pool: FakePool) -> None:
    inv_repo = InvestigationRepo(fake_pool)
    entity_id = uuid4()
    inv_id = await inv_repo.create(
        target_entity_id=entity_id,
        country="pe",
        locale="es",
        user_id=None,
    )
    # The FakePool only stores the basics; fill in fields the model needs so we can read back.
    from datetime import UTC, datetime

    fake_pool.investigations[inv_id] = {
        "id": inv_id,
        "target_entity_id": entity_id,
        "country": "pe",
        "locale": "es",
        "status": "pending",
        "plan": "[]",  # exercise the JSON-string branch in repo.get
        "dossier_md": None,
        "cost_usd": 0,
        "progress_pct": 0,
        "is_public": True,
        "started_at": datetime.now(UTC),
        "finished_at": None,
    }
    got = await inv_repo.get(inv_id)
    assert isinstance(got, Investigation)
    assert got.id == inv_id
    assert got.plan == []


@pytest.mark.asyncio
async def test_investigation_repo_enqueue_pushes_to_pgmq(fake_pool: FakePool) -> None:
    inv_repo = InvestigationRepo(fake_pool)
    inv_id = uuid4()
    await inv_repo.enqueue(inv_id, "investigation_queue")
    assert fake_pool.enqueued == [
        {"queue": "investigation_queue", "payload": f'{{"investigation_id": "{inv_id}"}}'}
    ]


@pytest.mark.asyncio
async def test_event_repo_returns_only_events_after_last_id(fake_pool: FakePool) -> None:
    inv_id = uuid4()
    fake_pool.events = [
        {"id": 1, "investigation_id": inv_id, "type": "heartbeat", "payload": {}},
        {"id": 2, "investigation_id": inv_id, "type": "heartbeat", "payload": {}},
        {"id": 3, "investigation_id": inv_id, "type": "heartbeat", "payload": {}},
    ]
    repo = EventRepo(fake_pool)
    rows = await repo.list_since(inv_id, last_event_id=1)
    assert [r["id"] for r in rows] == [2, 3]
