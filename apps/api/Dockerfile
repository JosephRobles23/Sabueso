# syntax=docker/dockerfile:1.7
# Multi-stage build for Sabueso API. Target image <300MB.

# ---------- Stage 1: builder ----------
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# uv = fast resolver/installer; ~10MB statically-linked binary.
COPY --from=ghcr.io/astral-sh/uv:0.5.7 /uv /usr/local/bin/uv

WORKDIR /app

# Copy lockfile + project metadata first so dependency layer can cache.
COPY pyproject.toml uv.lock ./

RUN uv venv /opt/venv && \
    uv sync --frozen --no-dev --no-install-project

# Now copy source and install the project itself.
COPY src ./src
RUN uv sync --frozen --no-dev


# ---------- Stage 2: runtime ----------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080

# Non-root user — Cloud Run accepts this and it shrinks the attack surface.
RUN groupadd --system sabueso && \
    useradd --system --gid sabueso --home-dir /app --shell /sbin/nologin sabueso && \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src ./src

USER sabueso

EXPOSE 8080

# Cloud Run injects $PORT — uvicorn binds to it. One worker (asyncio handles concurrency).
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips=*"]
