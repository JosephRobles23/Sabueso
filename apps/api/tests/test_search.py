from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import FakePool


@pytest.mark.asyncio
async def test_search_returns_hits(client: AsyncClient, fake_pool: FakePool) -> None:
    hit_id = uuid4()
    fake_pool.search_results = [
        {
            "id": hit_id,
            "country": "pe",
            "type": "person",
            "name": "Vladimir Cerrón",
            "identifier": "12345678",
            "score": 0.91,
        }
    ]
    resp = await client.get("/api/v1/search", params={"q": "cerron", "country": "pe"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "cerron"
    assert body["country"] == "pe"
    assert isinstance(body["took_ms"], int) and body["took_ms"] >= 0
    assert len(body["results"]) == 1
    assert body["results"][0]["id"] == str(hit_id)
    assert body["results"][0]["score"] == pytest.approx(0.91)


@pytest.mark.asyncio
async def test_search_requires_min_query_length(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/search", params={"q": "a"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_accepts_no_country(client: AsyncClient, fake_pool: FakePool) -> None:
    fake_pool.search_results = []
    resp = await client.get("/api/v1/search", params={"q": "anybody"})
    assert resp.status_code == 200
    assert resp.json()["country"] is None
