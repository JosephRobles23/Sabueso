"""Cliente HTTP compartido con retry exponencial + rate limiting.

- 5xx → retry exponencial (0.5s, 1s, 2s) hasta 3 intentos, después
  ``SourceUnavailableError``.
- 429 → ``RateLimitedError`` inmediato (la fuente nos pidió frenar, no
  insistimos).
- timeouts/connection errors → mismo budget que 5xx.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from .errors import RateLimitedError, SourceUnavailableError, ToolError
from .rate_limit import RateLimiter, get_rate_limiter

DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Sabueso/0.1 (+https://sabueso.dev; investigación periodística; "
        "contacto@sabueso.dev)"
    ),
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.6",
}
_RETRY_STATUS = {500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_BACKOFF = 0.5


async def _sleep_backoff(attempt: int) -> None:
    # 0.5, 1.0, 2.0 + jitter
    delay = _BASE_BACKOFF * (2**attempt) + random.uniform(0, 0.25)
    await asyncio.sleep(delay)


async def request(
    method: str,
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    rate_limiter: RateLimiter | None = None,
    tool: str | None = None,
    country: str | None = None,
    headers: dict[str, str] | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """Hace request HTTP con rate-limit + retry.

    Si ``client`` es ``None`` crea uno efímero. Para llamadas múltiples al
    mismo host conviene pasar un ``httpx.AsyncClient`` compartido para reutilizar
    pool de conexiones.
    """
    limiter = rate_limiter or get_rate_limiter()
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    owns_client = client is None

    async def _do(c: httpx.AsyncClient) -> httpx.Response:
        last_error: BaseException | None = None
        for attempt in range(_MAX_RETRIES):
            await limiter.acquire(url)
            try:
                response = await c.request(method, url, headers=merged_headers, **kwargs)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                last_error = exc
                if attempt < _MAX_RETRIES - 1:
                    await _sleep_backoff(attempt)
                    continue
                raise SourceUnavailableError(
                    f"network failure after {_MAX_RETRIES} attempts: {exc}",
                    tool=tool,
                    country=country,
                    cause=exc,
                ) from exc

            if response.status_code == 429:
                retry_after_raw = response.headers.get("retry-after")
                retry_after: float | None = None
                if retry_after_raw:
                    try:
                        retry_after = float(retry_after_raw)
                    except ValueError:
                        retry_after = None
                raise RateLimitedError(
                    f"upstream returned 429 (retry-after={retry_after_raw})",
                    retry_after=retry_after,
                    tool=tool,
                    country=country,
                )

            if response.status_code in _RETRY_STATUS:
                if attempt < _MAX_RETRIES - 1:
                    await _sleep_backoff(attempt)
                    continue
                raise SourceUnavailableError(
                    f"upstream returned {response.status_code} "
                    f"after {_MAX_RETRIES} attempts",
                    status_code=response.status_code,
                    tool=tool,
                    country=country,
                )

            return response

        raise SourceUnavailableError(
            "retry loop exhausted without response",
            tool=tool,
            country=country,
            cause=last_error,
        )

    if owns_client:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as c:
            return await _do(c)
    assert client is not None
    return await _do(client)


async def get(url: str, **kwargs: Any) -> httpx.Response:
    return await request("GET", url, **kwargs)


async def post(url: str, **kwargs: Any) -> httpx.Response:
    return await request("POST", url, **kwargs)


def raise_for_unexpected(
    response: httpx.Response,
    *,
    tool: str,
    country: str,
) -> None:
    """Convierte un response 4xx (≠429) en ``ToolError`` con contexto."""
    if 400 <= response.status_code < 500 and response.status_code != 429:
        raise ToolError(
            f"upstream returned {response.status_code}: {response.text[:200]}",
            tool=tool,
            country=country,
        )
