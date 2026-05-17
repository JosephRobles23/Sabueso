from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import FakePool


@pytest.mark.asyncio
async def test_get_entity_returns_404_when_missing(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/entities/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_entity_returns_record(
    client: AsyncClient, seed_entity: dict[str, object]
) -> None:
    resp = await client.get(f"/api/v1/entities/{seed_entity['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == seed_entity["name"]
    assert body["country"] == seed_entity["country"]


@pytest.mark.asyncio
async def test_list_claims_for_entity(
    client: AsyncClient, fake_pool: FakePool, seed_entity: dict[str, object]
) -> None:
    fake_pool.claims_by_entity[seed_entity["id"]] = [  # type: ignore[index]
        {
            "id": uuid4(),
            "predicate": "owns",
            "object_value": {"name": "Empresa SAC"},
            "source_id": uuid4(),
            "source_extract": "...",
            "confidence": 0.8,
            "agent_callsign": "el-contador",
            "verified_by_jueza": True,
            "created_at": None,
        }
    ]
    resp = await client.get(f"/api/v1/entities/{seed_entity['id']}/claims")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entity_id"] == str(seed_entity["id"])
    assert len(body["claims"]) == 1
    assert body["claims"][0]["predicate"] == "owns"
