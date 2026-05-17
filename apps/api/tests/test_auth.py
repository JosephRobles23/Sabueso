from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from jose import jwt
from jose.utils import long_to_base64

from src.auth.jwks import JWKSCache
from src.main import create_app
from src.settings import Settings


def _rsa_keypair() -> tuple[str, dict[str, str]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "test-key-1",
        "use": "sig",
        "alg": "RS256",
        "n": long_to_base64(pub_numbers.n).decode("ascii"),
        "e": long_to_base64(pub_numbers.e).decode("ascii"),
    }
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    return pem, jwk


def _build_app_with_mock_jwks(settings: Settings, keys: list[dict[str, str]]) -> tuple[Any, Any]:
    transport = httpx.MockTransport(lambda _req: httpx.Response(200, json={"keys": keys}))
    client = httpx.AsyncClient(transport=transport)
    cache = JWKSCache(settings.supabase_jwks_url or "https://fake/jwks", 300, client=client)

    app = create_app(settings)
    for mw in app.user_middleware:
        if mw.cls.__name__ == "AuthMiddleware":
            mw.kwargs["jwks"] = cache
    app.state.db_pool = None
    return app, client


@pytest.mark.asyncio
async def test_anonymous_request_passes_without_header() -> None:
    settings = Settings(
        supabase_db_url="postgresql://test",
        supabase_jwks_url="",  # JWKS disabled
        log_level="WARNING",
    )
    app = create_app(settings)
    app.state.db_pool = None

    async def whoami(request: Request) -> dict[str, bool]:
        return {"anonymous": getattr(request.state, "user", None) is None}

    app.add_api_route("/whoami", whoami, methods=["GET"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/whoami")
    assert resp.status_code == 200
    assert resp.json()["anonymous"] is True


@pytest.mark.asyncio
async def test_invalid_jwt_returns_401_when_jwks_configured() -> None:
    _, jwk = _rsa_keypair()
    settings = Settings(
        supabase_db_url="postgresql://test",
        supabase_jwks_url="https://fake/jwks",
        supabase_jwt_aud="authenticated",
        log_level="WARNING",
    )
    app, client = _build_app_with_mock_jwks(settings, [jwk])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/healthz", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401

    await client.aclose()


@pytest.mark.asyncio
async def test_valid_jwt_attaches_user() -> None:
    pem, jwk = _rsa_keypair()
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "aud": "authenticated", "email": "x@y.com"},
        pem,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )
    settings = Settings(
        supabase_db_url="postgresql://test",
        supabase_jwks_url="https://fake/jwks",
        supabase_jwt_aud="authenticated",
        log_level="WARNING",
    )
    app, client = _build_app_with_mock_jwks(settings, [jwk])

    captured: dict[str, Any] = {}

    async def whoami(request: Request) -> dict[str, Any]:
        user = getattr(request.state, "user", None)
        captured["user"] = user
        return {"id": str(user.id) if user else None, "email": user.email if user else None}

    app.add_api_route("/whoami", whoami, methods=["GET"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(user_id)
    assert body["email"] == "x@y.com"

    await client.aclose()


@pytest.mark.asyncio
async def test_malformed_authorization_header_returns_401() -> None:
    settings = Settings(
        supabase_db_url="postgresql://test",
        supabase_jwks_url="https://fake/jwks",
        log_level="WARNING",
    )
    app = create_app(settings)
    app.state.db_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/healthz", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_jwt_without_jwks_configured_is_ignored() -> None:
    """If JWKS isn't configured we don't enforce — request still goes through as anonymous."""
    settings = Settings(
        supabase_db_url="postgresql://test",
        supabase_jwks_url="",
        log_level="WARNING",
    )
    app = create_app(settings)
    app.state.db_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(
            "/api/v1/healthz",
            headers={"Authorization": "Bearer anything-goes"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_jwks_cache_only_fetches_once_within_ttl() -> None:
    call_count = {"n": 0}
    _, jwk = _rsa_keypair()

    def handler(_req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json={"keys": [jwk]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cache = JWKSCache("https://fake/jwks", ttl_seconds=300, client=client)

    assert await cache.get_key("test-key-1") is not None
    assert await cache.get_key("test-key-1") is not None
    assert call_count["n"] == 1

    await client.aclose()
