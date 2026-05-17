# syntax=docker/dockerfile:1.7
# Imagen del Cloud Run Job pipeline-ingest (S-15).
#
# Multi-stage:
#   1. builder — uv resuelve deps a /opt/venv
#   2. runtime — imagen ligera; java/tika opcionales para fallback de PDFs

# ---------- Stage 1: builder ----------
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=ghcr.io/astral-sh/uv:0.5.7 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./

# uv.lock se genera al build si no existe (uv sync resuelve y crea uno).
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python --no-cache \
        cocoindex>=1.0.0 \
        pymupdf>=1.25.0 \
        httpx>=0.28.0 \
        asyncpg>=0.30.0 \
        pydantic>=2.10.0 \
        structlog>=24.4.0 \
        google-cloud-storage>=2.19.0 \
        openai>=1.60.0 \
        python-dotenv>=1.0.0 \
        pyyaml>=6.0

COPY src ./src
COPY flows ./flows

RUN find /opt/venv -type d \( -name "__pycache__" -o -name "tests" -o -name "test" \) -prune -exec rm -rf {} + && \
    find /opt/venv -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete


# ---------- Stage 2: runtime ----------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app

# git: necesario para clone de legalize-pe en pe_legalize_flow.
# default-jre-headless + tika-app: fallback PDF (ligero, <200MB extra).
RUN groupadd --system sabueso && \
    useradd --system --gid sabueso --home-dir /home/sabueso --shell /sbin/nologin --create-home sabueso && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        default-jre-headless && \
    rm -rf /var/lib/apt/lists/*

# Tika app (opcional, controlado por TIKA_JAR env var en runtime)
ARG TIKA_VERSION=2.9.2
RUN mkdir -p /opt/tika && \
    curl -sSL -o /opt/tika/tika-app.jar \
        "https://archive.apache.org/dist/tika/${TIKA_VERSION}/tika-app-${TIKA_VERSION}.jar" \
    || echo "tika download skipped (offline build)"

ENV TIKA_JAR=/opt/tika/tika-app.jar

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src ./src
COPY --from=builder /app/flows ./flows

USER sabueso

ENTRYPOINT ["python", "-m", "src.main"]
