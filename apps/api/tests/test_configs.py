from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from src.auth.current_user import require_user
from src.auth.middleware import CurrentUser
from tests.conftest import FakePool


def _login_as(client: AsyncClient, user_id: UUID) -> CurrentUser:
    """Forzar require_user vía dependency_overrides.

    El AuthMiddleware real ya tiene tests; acá lo bypasseamos para enfocarnos
    en el comportamiento del route (filtrado por user_id, validación de
    callsign, merge JSONB).
    """
    user = CurrentUser(id=user_id, email="who@cares.dev", claims={})
    client.app.dependency_overrides[require_user] = lambda: user  # type: ignore[attr-defined]
    return user


@pytest.mark.asyncio
async def test_list_configs_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/configs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_configs_returns_only_caller_rows(
    client: AsyncClient, fake_pool: FakePool
) -> None:
    me = uuid4()
    other = uuid4()
    fake_pool.investigator_configs[(me, "el-contador")] = {
        "user_id": me, "callsign": "el-contador",
        "config": {"active": True, "model": "kimi-k2.6"},
        "created_at": None, "updated_at": None,
    }
    fake_pool.investigator_configs[(me, "el-periodista")] = {
        "user_id": me, "callsign": "el-periodista",
        "config": {"active": False},
        "created_at": None, "updated_at": None,
    }
    fake_pool.investigator_configs[(other, "el-contador")] = {
        "user_id": other, "callsign": "el-contador",
        "config": {"active": True},
        "created_at": None, "updated_at": None,
    }
    _login_as(client, me)

    resp = await client.get("/api/v1/configs")
    assert resp.status_code == 200
    body = resp.json()
    callsigns = [c["callsign"] for c in body["configs"]]
    assert callsigns == ["el-contador", "el-periodista"]
    assert all(UUID(c["user_id"]) == me for c in body["configs"])


@pytest.mark.asyncio
async def test_patch_unknown_callsign_returns_400(client: AsyncClient) -> None:
    _login_as(client, uuid4())
    resp = await client.patch(
        "/api/v1/configs/el-fantasma",
        json={"config": {"active": False}},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_patch_creates_row_when_missing(
    client: AsyncClient, fake_pool: FakePool
) -> None:
    me = uuid4()
    _login_as(client, me)

    resp = await client.patch(
        "/api/v1/configs/el-buscador",
        json={"config": {"active": False, "rules": "no buscar en redes"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["callsign"] == "el-buscador"
    assert body["config"]["active"] is False
    assert body["config"]["rules"] == "no buscar en redes"
    assert (me, "el-buscador") in fake_pool.investigator_configs


@pytest.mark.asyncio
async def test_patch_merges_existing_config(
    client: AsyncClient, fake_pool: FakePool
) -> None:
    me = uuid4()
    fake_pool.investigator_configs[(me, "la-tasadora")] = {
        "user_id": me,
        "callsign": "la-tasadora",
        "config": {"active": True, "model": "deepseek-v4-flash", "skills": ["sunarp"]},
        "created_at": None,
        "updated_at": None,
    }
    _login_as(client, me)

    resp = await client.patch(
        "/api/v1/configs/la-tasadora",
        json={"config": {"model": "claude-sonnet-4.6"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    cfg: dict[str, Any] = body["config"]
    # Campo sobreescrito
    assert cfg["model"] == "claude-sonnet-4.6"
    # Campos preexistentes se preservan (shallow merge)
    assert cfg["active"] is True
    assert cfg["skills"] == ["sunarp"]
