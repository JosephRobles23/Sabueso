"""Rate limiter por host.

Cada fuente externa (osce.gob.pe, manolo.pe, ...) tiene un bucket independiente.
Default 2 req/s por host, configurable por sitio.

Implementación: token bucket asíncrono per-host con asyncio.Lock para evitar
race conditions cuando dos coroutines pegan al mismo host concurrentemente.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class _Bucket:
    """Token bucket por host. ``capacity`` tokens, refill a ``rate``/s."""

    capacity: float
    rate: float
    tokens: float = field(init=False)
    updated_at: float = field(init=False)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.updated_at = time.monotonic()

    async def acquire(self) -> None:
        async with self.lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.updated_at
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.updated_at = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait)


class RateLimiter:
    """Registry de buckets indexados por host.

    Uso típico::

        limiter = RateLimiter(default_rate=2.0)
        limiter.set("contratacionesabiertas.osce.gob.pe", rate=1.0)
        await limiter.acquire("https://contratacionesabiertas.osce.gob.pe/...")
    """

    def __init__(self, default_rate: float = 2.0, default_capacity: float = 2.0) -> None:
        self._default_rate = default_rate
        self._default_capacity = default_capacity
        self._buckets: dict[str, _Bucket] = {}
        self._overrides: dict[str, tuple[float, float]] = {}
        self._registry_lock = asyncio.Lock()

    def set(self, host: str, *, rate: float, capacity: float | None = None) -> None:
        """Configura un host con rate distinto al default. Llamar al boot."""
        self._overrides[host] = (rate, capacity or rate)

    def _host_of(self, url_or_host: str) -> str:
        if "://" in url_or_host:
            host = urlparse(url_or_host).hostname or url_or_host
        else:
            host = url_or_host
        return host.lower()

    async def acquire(self, url_or_host: str) -> None:
        host = self._host_of(url_or_host)
        bucket = self._buckets.get(host)
        if bucket is None:
            async with self._registry_lock:
                bucket = self._buckets.get(host)
                if bucket is None:
                    rate, cap = self._overrides.get(
                        host, (self._default_rate, self._default_capacity)
                    )
                    bucket = _Bucket(capacity=cap, rate=rate)
                    self._buckets[host] = bucket
        await bucket.acquire()


_default_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Singleton perezoso. Tests pueden reemplazarlo vía ``set_rate_limiter``."""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter(default_rate=2.0, default_capacity=2.0)
    return _default_limiter


def set_rate_limiter(limiter: RateLimiter | None) -> None:
    global _default_limiter
    _default_limiter = limiter
