from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "sabueso-api"
    environment: str = Field(default="dev", description="dev|staging|prod")
    log_level: str = "INFO"

    api_prefix: str = "/api/v1"
    port: int = Field(default=8000, ge=1, le=65535)

    # CORS — explicit list, no wildcards in prod.
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "https://sabueso.vercel.app",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # Supabase / DB
    supabase_db_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/postgres",
        description="Full async-compatible DSN; asyncpg ignores ?sslmode params",
    )
    supabase_url: str = Field(default="")
    supabase_service_role_key: str = Field(default="")
    supabase_jwks_url: str = Field(
        default="",
        description="Optional. If empty, JWT validation is skipped and requests are anonymous.",
    )
    supabase_jwt_aud: str = "authenticated"
    supabase_jwt_iss: str = ""

    # asyncpg pool — Supabase free tier caps at 60 direct connections.
    db_pool_min_size: int = Field(default=5, ge=1)
    db_pool_max_size: int = Field(default=20, ge=1)
    db_pool_command_timeout: float = Field(default=10.0, gt=0)

    # JWKS cache TTL
    jwks_cache_ttl_seconds: int = Field(default=300, ge=30)

    # Worker dispatch (S-07 will fill these in)
    gcp_project_id: str = ""
    gcp_region: str = "southamerica-east1"
    worker_job_name: str = "sabueso-investigation-worker"
    dispatch_worker: bool = False  # off by default until S-07 lands

    # pgmq queue name
    pgmq_queue: str = "investigation_queue"

    # Vercel KV — second-layer rate limit (defense in depth, S-20).
    # Empty values disable backend enforcement; Edge layer remains primary.
    vercel_kv_rest_api_url: str = ""
    vercel_kv_rest_api_token: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
