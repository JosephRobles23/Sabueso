#!/usr/bin/env bash
# Build and deploy the Sabueso investigation worker as a Cloud Run Job.
#
# Requires: gcloud auth login + gcloud config set project $GCP_PROJECT_ID
# Env (all overridable):
#   PROJECT_ID       — GCP project (defaults to $GCP_PROJECT_ID)
#   REGION           — Cloud Run region (default southamerica-east1)
#   JOB              — Cloud Run Job name (default investigation-worker)
#   REPO             — Artifact Registry repo (default sabueso)
#   IMAGE_NAME       — image name within REPO (default sabueso-worker)
#   TAG              — image tag (default: short git sha, or "latest")
#   SERVICE_ACCOUNT  — runtime SA email (required)
#   TASK_TIMEOUT     — per-task timeout in seconds (default 3600)
#   MEMORY           — memory per task (default 2Gi)
#   CPU              — cpu per task (default 2)
#   MAX_RETRIES      — task retries (default 1)
#   SECRETS          — comma-separated --set-secrets list (optional)
#   EXTRA_ENV        — comma-separated --set-env-vars list (optional)

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-${GCP_PROJECT_ID:-}}"
REGION="${REGION:-${GCP_REGION:-southamerica-east1}}"
JOB="${JOB:-investigation-worker}"
REPO="${REPO:-sabueso}"
IMAGE_NAME="${IMAGE_NAME:-sabueso-worker}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}"
TASK_TIMEOUT="${TASK_TIMEOUT:-3600}"
MEMORY="${MEMORY:-2Gi}"
CPU="${CPU:-2}"
MAX_RETRIES="${MAX_RETRIES:-1}"
SECRETS="${SECRETS:-}"
EXTRA_ENV="${EXTRA_ENV:-}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID (or GCP_PROJECT_ID) is required" >&2
  exit 1
fi
if [[ -z "${SERVICE_ACCOUNT}" ]]; then
  echo "SERVICE_ACCOUNT (runtime SA email) is required" >&2
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}"

echo "==> Building ${IMAGE}"
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --tag="${IMAGE}" \
  .

# `gcloud run jobs deploy` is upsert: creates the job on first run, updates after.
# Keeping the flag list aligned with infra/cloudrun/jobs/investigation-worker.yaml.
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
  --labels=app=sabueso,component=worker
  --set-env-vars="LOG_LEVEL=INFO,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION}${EXTRA_ENV:+,${EXTRA_ENV}}"
)

if [[ -n "${SECRETS}" ]]; then
  DEPLOY_ARGS+=(--set-secrets="${SECRETS}")
fi

echo "==> Deploying Cloud Run Job ${JOB} (${REGION})"
gcloud run jobs deploy "${DEPLOY_ARGS[@]}"

echo "==> Done. Job description:"
gcloud run jobs describe "${JOB}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(metadata.name,spec.template.spec.template.spec.containers[0].image)'
