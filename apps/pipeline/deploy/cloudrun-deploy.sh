#!/usr/bin/env bash
# Build + deploy del Cloud Run Job pipeline-ingest (S-15).
#
# Requiere: gcloud auth + gcloud config set project
# Env (overridables):
#   PROJECT_ID       — GCP project (default: $GCP_PROJECT_ID)
#   REGION           — Cloud Run region (default: southamerica-east1)
#   JOB              — nombre del job (default: pipeline-ingest)
#   REPO             — Artifact Registry repo (default: sabueso)
#   IMAGE_NAME       — imagen dentro del repo (default: sabueso-pipeline)
#   TAG              — tag (default: git short sha)
#   SERVICE_ACCOUNT  — runtime SA email (required)
#   TASK_TIMEOUT     — segundos (default 21600 = 6h)
#   MEMORY           — default 4Gi (PyMuPDF + tika + clones)
#   CPU              — default 2
#   SECRETS          — --set-secrets list (opcional)
#   EXTRA_ENV        — --set-env-vars adicionales (opcional)

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-${GCP_PROJECT_ID:-}}"
REGION="${REGION:-${GCP_REGION:-southamerica-east1}}"
JOB="${JOB:-pipeline-ingest}"
REPO="${REPO:-sabueso}"
IMAGE_NAME="${IMAGE_NAME:-sabueso-pipeline}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}"
TASK_TIMEOUT="${TASK_TIMEOUT:-21600}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
MAX_RETRIES="${MAX_RETRIES:-1}"
SECRETS="${SECRETS:-}"
EXTRA_ENV="${EXTRA_ENV:-}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID (o GCP_PROJECT_ID) requerido" >&2
  exit 1
fi
if [[ -z "${SERVICE_ACCOUNT}" ]]; then
  echo "SERVICE_ACCOUNT (runtime SA email) requerido" >&2
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}"

echo "==> Build ${IMAGE}"
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --tag="${IMAGE}" \
  .

DEPLOY_ARGS=(
  "${JOB}"
  --project="${PROJECT_ID}"
  --region="${REGION}"
  --image="${IMAGE}"
  --service-account="${SERVICE_ACCOUNT}"
  --task-timeout="${TASK_TIMEOUT}"
  --memory="${MEMORY}"
  --cpu="${CPU}"
  --max-retries="${MAX_RETRIES}"
  --parallelism=1
  --tasks=1
  --labels=app=sabueso,component=pipeline
  --set-env-vars="LOG_LEVEL=INFO,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},PIPELINE_FLOW=all${EXTRA_ENV:+,${EXTRA_ENV}}"
)

if [[ -n "${SECRETS}" ]]; then
  DEPLOY_ARGS+=(--set-secrets="${SECRETS}")
fi

echo "==> Deploy Cloud Run Job ${JOB} (${REGION})"
gcloud run jobs deploy "${DEPLOY_ARGS[@]}"

echo "==> Job desplegado:"
gcloud run jobs describe "${JOB}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(metadata.name,spec.template.spec.template.spec.containers[0].image)'
