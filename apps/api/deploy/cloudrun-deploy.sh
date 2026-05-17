#!/usr/bin/env bash
# Deploy Sabueso API to Cloud Run.
# Requires: gcloud auth login + gcloud config set project $GCP_PROJECT_ID
# Env: PROJECT_ID, REGION (default southamerica-east1), IMAGE (default sabueso-api), SERVICE.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-${GCP_PROJECT_ID:-}}"
REGION="${REGION:-${GCP_REGION:-southamerica-east1}}"
SERVICE="${SERVICE:-sabueso-api}"
REPO="${REPO:-sabueso}"
IMAGE_NAME="${IMAGE_NAME:-${SERVICE}}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID (or GCP_PROJECT_ID) is required" >&2
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}"

echo "==> Building ${IMAGE}"
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --tag="${IMAGE}" \
  .

echo "==> Deploying ${SERVICE} to Cloud Run (${REGION})"
gcloud run deploy "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=1 \
  --max-instances=10 \
  --concurrency=80 \
  --timeout=3600 \
  --cpu=1 \
  --memory=1Gi \
  --no-cpu-throttling \
  --port=8080 \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},LOG_LEVEL=INFO" \
  --set-secrets="SUPABASE_DB_URL=supabase-db-url:latest,SUPABASE_SERVICE_ROLE_KEY=supabase-service-role-key:latest,SUPABASE_JWKS_URL=supabase-jwks-url:latest"

echo "==> Done. Service URL:"
gcloud run services describe "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)'
