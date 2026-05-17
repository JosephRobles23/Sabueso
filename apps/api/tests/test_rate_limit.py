from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest
from starlette.requests import Request

from src.auth.middleware import CurrentUser
from src.auth.rate_limit import (
    RATE_LIMITS,
    VercelKVClient,
    _bucket_for,
    _slot_key,
    check_rate_limit,
    enforce_rate_limit,
)


class FakeApp:
    def __init__(self, kv: Any) -> None:
        self.state = type("S", (), {"kv_client": kv})()


def _request(*, user: CurrentUser | None = None, ip: str = "1.2.3.4") -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/investigate",
        "headers": [(b"x-forwarded-for", ip.encode())],
        "query_string": b"",
        "client": ("test", 0),
    }
    req = Request(scope)
    req.state.user = user
    return req


def _attach_app(req: Request, kv: Any) -> Request:
    req.scope["app"] = FakeApp(kv)
    return req


class FakeKV:
    """Tracks INCR / EXPIRE calls. Returns programmable counts."""

    def __init__(self, *, raise_on: str | None = None) -> None:
        self.counts: dict[str, int] = {}
        self.expires: dict[str, int] = {}
        self._raise_on = raise_on

    async def incr_with_expire(self, key: str, ttl_seconds: int) -> int:
        if self._raise_on == "incr":
            raise httpx.ConnectError("kv down")
        self.counts[key] = self.counts.get(key, 0) + 1
        self.expires[key] = ttl_seconds
        return self.counts[key]


def test_bucket_inference_anonymous_uses_ip() -> None:
    req = _request(user=None, ip="9.9.9.9")
    bucket, ident = _bucket_for(req)
    assert bucket == "anon"
    assert ident == "ip:9.9.9.9"


def test_bucket_inference_authenticated_uses_user_id() -> None:
    user = CurrentUser(id=uuid4(), email=None, claims={})
    bucket, ident = _bucket_for(_request(user=user))
    assert bucket == "auth"
    assert ident.startswith("user:")


def test_bucket_override_search_uses_ip_even_for_auth_user() -> None:
    user = CurrentUser(id=uuid4(), email=None, claims={})
    bucket, ident = _bucket_for(_request(user=user, ip="5.5.5.5"), override="search")
    assert bucket == "search"
    assert ident == "ip:5.5.5.5"


def test_slot_key_changes_per_window() -> None:
    a = _slot_key("anon", "ip:1.1.1.1", window_seconds=60 * 60 * 24)
    b = _slot_key("anon", "ip:1.1.1.1", window_seconds=1)
    # Different windows → different slot ints → different keys.
    assert a != b


@pytest.mark.asyncio
async def test_check_rate_limit_no_kv_fails_open() -> None:
    req = _attach_app(_request(), kv=None)
    decision = await check_rate_limit(req)
    assert decision.allowed
    assert decision.bucket == "anon"
    assert decision.limit == RATE_LIMITS["anon"].limit


@pytest.mark.asyncio
async def test_check_rate_limit_under_limit_allows() -> None:
    kv = FakeKV()
    req = _attach_app(_request(), kv=kv)
    decision = await check_rate_limit(req)
    assert decision.allowed
    assert decision.remaining == RATE_LIMITS["anon"].limit - 1


@pytest.mark.asyncio
async def test_check_rate_limit_blocks_when_over_limit() -> None:
    kv = FakeKV()
    req = _attach_app(_request(), kv=kv)
    limit = RATE_LIMITS["anon"].limit
    for _ in range(limit):
        decision = await check_rate_limit(req)
        assert decision.allowed
    # One more → blocked.
    decision = await check_rate_limit(req)
    assert not decision.allowed
    assert decision.remaining == 0


@pytest.mark.asyncio
async def test_check_rate_limit_kv_error_fails_open() -> None:
    kv = FakeKV(raise_on="incr")
    req = _attach_app(_request(), kv=kv)
    decision = await check_rate_limit(req)
    assert decision.allowed  # fail-open
    assert decision.remaining == RATE_LIMITS["anon"].limit


@pytest.mark.asyncio
async def test_enforce_rate_limit_raises_429_when_over_budget() -> None:
    from fastapi import HTTPException

    kv = FakeKV()
    req = _attach_app(_request(), kv=kv)
    # Saturate
    for _ in range(RATE_LIMITS["anon"].limit):
        await enforce_rate_limit(req)
    with pytest.raises(HTTPException) as exc:
        await enforce_rate_limit(req)
    assert exc.value.status_code == 429
    assert exc.value.headers is not None
    assert "Retry-After" in exc.value.headers


@pytest.mark.asyncio
async def test_vercel_kv_client_constructs_pipeline_request() -> None:
    """Sanity check the wire format we send to Vercel KV /pipeline."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json=[{"result": 1}, {"result": 1}])

    transport = httpx.MockTransport(handler)
    client = VercelKVClient("https://kv.example.com", "tok")
    client._client = httpx.AsyncClient(  # noqa: SLF001 — test seam
        transport=transport,
        headers={"Authorization": "Bearer tok", "Content-Type": "application/json"},
    )
    count = await client.incr_with_expire("rl:anon:ip:1.1.1.1:1", 60)
    await client.aclose()
    assert count == 1
    assert captured["url"].endswith("/pipeline")
    assert "INCR" in captured["body"]
    assert "EXPIRE" in captured["body"]
