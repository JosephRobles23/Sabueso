from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


class JWKSCache:
    """In-process JWKS cache with TTL. One refresh in flight at a time."""

    def __init__(
        self,
        url: str,
        ttl_seconds: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = url
        self._ttl = ttl_seconds
        self._client = client or httpx.AsyncClient(timeout=5.0)
        self._owns_client = client is None
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def url(self) -> str:
        return self._url

    def _expired(self) -> bool:
        return (time.monotonic() - self._fetched_at) >= self._ttl

    async def get_key(self, kid: str) -> dict[str, Any] | None:
        if not self._keys or self._expired():
            await self._refresh()
        return self._keys.get(kid)

    async def _refresh(self) -> None:
        async with self._lock:
            if self._keys and not self._expired():
                return
            resp = await self._client.get(self._url)
            resp.raise_for_status()
            payload = resp.json()
            self._keys = {k["kid"]: k for k in payload.get("keys", []) if "kid" in k}
            self._fetched_at = time.monotonic()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
