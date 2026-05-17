"""Second-layer rate limit at the API.

The Vercel Edge middleware (apps/web/middleware.ts) is the primary enforcement
point. This module is a defense-in-depth check so that requests that bypass
the Edge (direct curl, server-to-server, future mobile client) still hit the
same buckets backed by the same Vercel KV instance.

Buckets mirror the Edge layer:
    - anon  : 10 / IP   / 24h
    - auth  : 50 / user / 24h
    - search: 300 / IP / 1h
    - pdf   : 20 / IP / 24h

Fail-open: if KV is unreachable or unconfigured, requests are allowed and a
warning is logged. Rate limiting is a guardrail, not authentication.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import httpx
import structlog
from fastapi import HTTPException, Request, status

log = structlog.get_logger(__name__)

Bucket = Literal["anon", "auth", "search", "pdf"]


@dataclass(frozen=True)
class BucketConfig:
    limit: int
    window_seconds: int


RATE_LIMITS: dict[Bucket, BucketConfig] = {
    "anon": BucketConfig(limit=10, window_seconds=60 * 60 * 24),
    "auth": BucketConfig(limit=50, window_seconds=60 * 60 * 24),
    "search": BucketConfig(limit=300, window_seconds=60 * 60),
    "pdf": BucketConfig(limit=20, window_seconds=60 * 60 * 24),
}


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    bucket: Bucket
    limit: int
    remaining: int
    reset_seconds: int
    identifier: str


class VercelKVClient:
    """Thin async wrapper over the Vercel KV REST API (pipeline endpoint).

    A single shared httpx.AsyncClient is used to keep connection reuse across
    requests in the Cloud Run container. Caller is responsible for closing it
    at shutdown (see lifespan in main.py).
    """

    def __init__(self, url: str, token: str, *, timeout: float = 1.0) -> None:
        self._base_url = url.rstrip("/")
        self._token = token
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def incr_with_expire(self, key: str, ttl_seconds: int) -> int:
        """INCR + (conditional) EXPIRE in a single pipelined round-trip.

        Vercel KV's /pipeline endpoint runs the commands sequentially in one
        connection. We always send EXPIRE — Redis treats EXPIRE on an existing
        TTL as an idempotent reset only if we passed XX; without it, repeated
        sets just keep the same TTL when the key was set by us, which is fine
        for sliding windows aligned to wall-clock slots.
        """
        resp = await self._client.post(
            f"{self._base_url}/pipeline",
            json=[["INCR", key], ["EXPIRE", key, ttl_seconds, "NX"]],
        )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, list) or not payload:
            raise RuntimeError(f"unexpected KV response: {payload!r}")
        count = payload[0].get("result")
        return int(count) if count is not None else 0


def _slot_key(bucket: Bucket, identifier: str, window_seconds: int) -> str:
    slot = int(time.time() // window_seconds)
    return f"rl:{bucket}:{identifier}:{slot}"


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real
    return request.client.host if request.client else "0.0.0.0"


def _bucket_for(request: Request, *, override: Bucket | None = None) -> tuple[Bucket, str]:
    if override is not None:
        ident = _identifier_for(request, override)
        return override, ident
    user = getattr(request.state, "user", None)
    if user is not None:
        return "auth", f"user:{user.id}"
    return "anon", f"ip:{_client_ip(request)}"


def _identifier_for(request: Request, bucket: Bucket) -> str:
    if bucket == "auth":
        user = getattr(request.state, "user", None)
        if user is not None:
            return f"user:{user.id}"
    return f"ip:{_client_ip(request)}"


async def enforce_rate_limit(
    request: Request,
    *,
    bucket: Bucket | None = None,
) -> RateLimitDecision:
    """Enforce the rate limit; raise 429 if over budget.

    Use as a FastAPI dependency on the routes that need backend enforcement
    (e.g. ``/investigate``, ``/search``, ``/export-pdf``). If ``bucket`` is
    omitted, the bucket is inferred from request.state.user (anon vs auth).
    """
    decision = await check_rate_limit(request, bucket=bucket)
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limited",
                "bucket": decision.bucket,
                "limit": decision.limit,
            },
            headers={
                "Retry-After": str(decision.reset_seconds),
                "X-RateLimit-Limit": str(decision.limit),
                "X-RateLimit-Remaining": str(decision.remaining),
                "X-RateLimit-Bucket": decision.bucket,
            },
        )
    return decision


async def check_rate_limit(
    request: Request,
    *,
    bucket: Bucket | None = None,
) -> RateLimitDecision:
    """Non-throwing variant; returns a decision the caller can inspect."""
    actual_bucket, identifier = _bucket_for(request, override=bucket)
    cfg = RATE_LIMITS[actual_bucket]

    kv = _get_client(request)
    if kv is None:
        return RateLimitDecision(
            allowed=True,
            bucket=actual_bucket,
            limit=cfg.limit,
            remaining=cfg.limit,
            reset_seconds=cfg.window_seconds,
            identifier=identifier,
        )

    key = _slot_key(actual_bucket, identifier, cfg.window_seconds)
    try:
        count = await kv.incr_with_expire(key, cfg.window_seconds)
    except (httpx.HTTPError, RuntimeError) as exc:
        log.warning(
            "rate_limit.kv_error_fail_open",
            bucket=actual_bucket,
            identifier=identifier,
            error=str(exc),
        )
        return RateLimitDecision(
            allowed=True,
            bucket=actual_bucket,
            limit=cfg.limit,
            remaining=cfg.limit,
            reset_seconds=cfg.window_seconds,
            identifier=identifier,
        )

    remaining = max(0, cfg.limit - count)
    return RateLimitDecision(
        allowed=count <= cfg.limit,
        bucket=actual_bucket,
        limit=cfg.limit,
        remaining=remaining,
        reset_seconds=cfg.window_seconds,
        identifier=identifier,
    )


def _get_client(request: Request) -> VercelKVClient | None:
    return getattr(request.app.state, "kv_client", None)


def build_kv_client(url: str, token: str) -> VercelKVClient | None:
    """Construct a KV client; returns None when not configured.

    Called once at FastAPI lifespan startup; attach to app.state.kv_client.
    """
    if not url or not token:
        return None
    return VercelKVClient(url=url, token=token)


__all__ = [
    "Bucket",
    "BucketConfig",
    "RATE_LIMITS",
    "RateLimitDecision",
    "VercelKVClient",
    "build_kv_client",
    "check_rate_limit",
    "enforce_rate_limit",
]
