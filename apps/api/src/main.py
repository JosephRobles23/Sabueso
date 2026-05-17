from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.jwks import JWKSCache
from src.auth.middleware import AuthMiddleware
from src.db.pool import create_pool
from src.observability.logging import configure_logging
from src.routes import entities_router, health_router, investigate_router, search_router
from src.settings import Settings, get_settings

log = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    jwks_cache: JWKSCache | None = (
        JWKSCache(settings.supabase_jwks_url, settings.jwks_cache_ttl_seconds)
        if settings.supabase_jwks_url
        else None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.jwks = jwks_cache
        try:
            app.state.db_pool = await create_pool(settings)
            log.info(
                "api.pool_ready",
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
            )
        except Exception as exc:
            # Don't crash the container — readyz will report db=fail so Cloud Run
            # holds traffic until the DB recovers (or the container is replaced).
            log.error("api.pool_init_failed", error=str(exc))
            app.state.db_pool = None

        try:
            yield
        finally:
            pool = getattr(app.state, "db_pool", None)
            if pool is not None:
                await pool.close()
            if jwks_cache is not None:
                await jwks_cache.close()

    app = FastAPI(
        title="Sabueso API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(
        AuthMiddleware,
        jwks=jwks_cache,
        audience=settings.supabase_jwt_aud,
        issuer=settings.supabase_jwt_iss,
    )

    prefix = settings.api_prefix
    app.include_router(health_router, prefix=prefix)
    app.include_router(investigate_router, prefix=prefix)
    app.include_router(search_router, prefix=prefix)
    app.include_router(entities_router, prefix=prefix)

    return app


app = create_app()
