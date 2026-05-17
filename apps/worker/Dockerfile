# syntax=docker/dockerfile:1.7
# Multi-stage build for the Sabueso investigation worker. Target image <500MB.
#
# - Python 3.12 slim + uv for fast, deterministic dep installs from uv.lock
# - Scrapling and the rest of the runtime deps baked into /opt/venv
# - Playwright Python package is included (browser extra) but its browser
#   binaries are NOT downloaded at build time. They're fetched on first use
#   by the orchestrator via `playwright install chromium`, which keeps the
#   shipped image lean (~400MB instead of ~1.3GB with chromium baked in).

# ---------- Stage 1: builder ----------
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# uv: ~10MB statically-linked binary.
COPY --from=ghcr.io/astral-sh/uv:0.5.7 /uv /usr/local/bin/uv

WORKDIR /app

# Lockfile + project metadata first so the heavy dep layer caches.
COPY pyproject.toml uv.lock ./

# `--extra browser` pulls in the playwright Python lib (used lazily — see note above).
RUN uv venv /opt/venv && \
    uv sync --frozen --no-dev --extra browser --no-install-project

# Then bring in source and install the project itself.
COPY src ./src
RUN uv sync --frozen --no-dev --extra browser

# Strip cached bytecode noise and tests-shipped-in-wheels to keep the runtime layer lean.
RUN find /opt/venv -type d \( -name "__pycache__" -o -name "tests" -o -name "test" \) -prune -exec rm -rf {} + && \
    find /opt/venv -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete


# ---------- Stage 2: runtime ----------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/home/sabueso/.cache/ms-playwright

# Non-root user; ca-certificates for outbound TLS to OpenRouter / GCS / scraping targets.
RUN groupadd --system sabueso && \
    useradd --system --gid sabueso --home-dir /home/sabueso --shell /sbin/nologin --create-home sabueso && \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src ./src

USER sabueso

# Cloud Run Jobs injects CLOUD_RUN_TASK_* env vars and overrides for INVESTIGATION_ID.
ENTRYPOINT ["python", "-m", "src.main"]
