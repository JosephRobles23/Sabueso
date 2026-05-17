"""Cliente HTTP reutilizable con retries + throttling.

Algunos endpoints (JNE, SEACE) rate-limitan agresivamente — concentramos la
política de reintentos acá en lugar de duplicarla en cada flow.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from .logging import get_logger

log = get_logger("sabueso.pipeline.http")


DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DEFAULT_HEADERS = {
    "User-Agent": "sabueso-pipeline/0.1 (+https://sabueso.dev)",
    "Accept-Language": "es-PE,es;q=0.9",
}


@asynccontextmanager
async def client(
    *,
    base_url: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | httpx.Timeout | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    async with httpx.AsyncClient(
        base_url=base_url or "",
        headers=merged_headers,
        timeout=timeout or DEFAULT_TIMEOUT,
        follow_redirects=True,
    ) as c:
        yield c


async def get_with_retries(
    c: httpx.AsyncClient,
    url: str,
    *,
    max_retries: int = 4,
    backoff_base: float = 1.5,
    accept_status: tuple[int, ...] = (200,),
    **kwargs,
) -> httpx.Response:
    """GET con backoff exponencial sobre status 429/5xx o errores de red."""
    attempt = 0
    while True:
        try:
            resp = await c.get(url, **kwargs)
            if resp.status_code in accept_status:
                return resp
            if resp.status_code < 500 and resp.status_code != 429:
                return resp  # 4xx no transitorio — devolvemos al caller
        except (httpx.TransportError, httpx.TimeoutException) as e:
            log.warning("http.transport_error", url=url, error=str(e), attempt=attempt)
            resp = None  # type: ignore[assignment]
        attempt += 1
        if attempt > max_retries:
            if resp is not None:
                return resp
            raise RuntimeError(f"GET {url}: agotados {max_retries} reintentos")
        wait = backoff_base**attempt
        log.warning(
            "http.retry",
            url=url,
            status=getattr(resp, "status_code", None),
            wait_s=round(wait, 2),
            attempt=attempt,
        )
        await asyncio.sleep(wait)
