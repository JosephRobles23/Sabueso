"""Tests del cliente HTTP con retry exponencial y manejo de 429/5xx."""

from __future__ import annotations

import pytest

from src.tools import http
from src.tools.errors import RateLimitedError, SourceUnavailableError
from src.tools.rate_limit import RateLimiter, set_rate_limiter


class _FakeResponse:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.text = ""
        self.content = b""


class _FakeClient:
    """Mock que devuelve la secuencia de status codes pasada."""

    def __init__(self, statuses: list[int], retry_after: str | None = None) -> None:
        self.statuses = list(statuses)
        self.retry_after = retry_after
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def request(self, method, url, **kwargs):
        self.calls += 1
        if not self.statuses:
            raise AssertionError("ran out of fake responses")
        code = self.statuses.pop(0)
        headers = {"retry-after": self.retry_after} if self.retry_after else {}
        return _FakeResponse(code, headers=headers)


@pytest.fixture(autouse=True)
def _fast_limiter():
    """Limiter generoso para no enlentecer los tests."""
    set_rate_limiter(RateLimiter(default_rate=1000.0, default_capacity=1000.0))
    yield
    set_rate_limiter(None)


@pytest.mark.asyncio
async def test_retries_on_5xx_then_succeeds():
    fake = _FakeClient([502, 503, 200])
    resp = await http.request("GET", "https://example.com/", client=fake)  # type: ignore[arg-type]
    assert resp.status_code == 200
    assert fake.calls == 3


@pytest.mark.asyncio
async def test_gives_up_after_three_5xx():
    fake = _FakeClient([500, 500, 500])
    with pytest.raises(SourceUnavailableError) as exc_info:
        await http.request(
            "GET",
            "https://example.com/",
            client=fake,  # type: ignore[arg-type]
            tool="t",
            country="pe",
        )
    assert exc_info.value.status_code == 500
    assert fake.calls == 3


@pytest.mark.asyncio
async def test_429_raises_rate_limited_with_retry_after():
    fake = _FakeClient([429], retry_after="30")
    with pytest.raises(RateLimitedError) as exc_info:
        await http.request(
            "GET",
            "https://example.com/",
            client=fake,  # type: ignore[arg-type]
            tool="t",
            country="pe",
        )
    assert exc_info.value.retry_after == 30.0
    assert fake.calls == 1  # no retry on 429


@pytest.mark.asyncio
async def test_2xx_returns_immediately():
    fake = _FakeClient([200])
    resp = await http.request("GET", "https://example.com/", client=fake)  # type: ignore[arg-type]
    assert resp.status_code == 200
    assert fake.calls == 1
