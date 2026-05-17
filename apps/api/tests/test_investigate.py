from __future__ import annotations

import time
from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.conftest import FakePool


@pytest.mark.asyncio
async def test_investigate_returns_202_with_ids(
    client: AsyncClient, fake_pool: FakePool
) -> None:
    resp = await client.post(
        "/api/v1/investigate",
        json={"entity_query": "Vladimir Cerrón", "country": "pe", "locale": "es"},
    )
    assert resp.status_code == 202
    body = resp.json()
    investigation_id = UUID(body["investigation_id"])
    entity_id = UUID(body["entity_id"])
    assert body["status"] == "pending"
    assert investigation_id in fake_pool.investigations
    assert entity_id in fake_pool.entities
    # Ensure the pgmq enqueue happened with the new id.
    assert len(fake_pool.enqueued) == 1
    payload = fake_pool.enqueued[0]
    assert payload["queue"] == "investigation_queue"
    assert str(investigation_id) in payload["payload"]


@pytest.mark.asyncio
async def test_investigate_reuses_existing_entity(
    client: AsyncClient, fake_pool: FakePool, seed_entity: dict[str, object]
) -> None:
    resp = await client.post(
        "/api/v1/investigate",
        json={
            "entity_query": str(seed_entity["name"]),
            "country": seed_entity["country"],
            "locale": "es",
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert UUID(body["entity_id"]) == seed_entity["id"]


@pytest.mark.asyncio
async def test_investigate_validates_input(client: AsyncClient) -> None:
    # entity_query too short
    resp = await client.post(
        "/api/v1/investigate",
        json={"entity_query": "x", "country": "pe", "locale": "es"},
    )
    assert resp.status_code == 422

    # invalid country
    resp = await client.post(
        "/api/v1/investigate",
        json={"entity_query": "Some Person", "country": "us", "locale": "es"},
    )
    assert resp.status_code == 422

    # malformed locale
    resp = await client.post(
        "/api/v1/investigate",
        json={"entity_query": "Some Person", "country": "pe", "locale": "BAD"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_investigate_meets_latency_budget(client: AsyncClient) -> None:
    """SLA in the spec: 202 in <500ms with the mocked DB. Real Postgres may be slower."""
    started = time.perf_counter()
    resp = await client.post(
        "/api/v1/investigate",
        json={"entity_query": "Latency Test", "country": "pe", "locale": "es"},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert resp.status_code == 202
    assert elapsed_ms < 500, f"investigate took {elapsed_ms:.0f}ms"
