from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import FakePool


@pytest.mark.asyncio
async def test_healthz_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz_ok_when_db_responds(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"db": "ok", "supabase": "ok"}


@pytest.mark.asyncio
async def test_readyz_503_when_db_fails(client: AsyncClient, fake_pool: FakePool) -> None:
    fake_pool.fail_healthcheck = True
    resp = await client.get("/api/v1/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["db"] == "fail"
    assert body["supabase"] == "fail"
