#!/usr/bin/env bash
# scripts/smoke-test.sh — primer E2E (S-10).
#
# Crea una investigación contra la entity demo de MINSA, drena el SSE
# durante ≤30s y verifica que el endpoint REST refleja status=complete.
#
# Uso:
#   API_BASE=https://api.staging.sabueso.app scripts/smoke-test.sh
#
# Variables:
#   API_BASE   — URL base del API (default: http://localhost:8000)
#   API_PREFIX — prefix de rutas (default: /api/v1)
#   API_TOKEN  — opcional; si está set, se envía como Bearer en POST + GET
#   ENTITY_QUERY — default: "MINSA"
#   COUNTRY    — default: "pe"
#   LOCALE     — default: "es"
#   SSE_TIMEOUT_S — default: 30
#   MIN_EVENTS — default: 3
#
# Exit codes:
#   0 — éxito (≥MIN_EVENTS SSE en <SSE_TIMEOUT_S y status=complete)
#   1 — POST falló o no devolvió investigation_id
#   2 — SSE no llegó al mínimo de eventos
#   3 — investigación quedó en estado distinto a 'complete'

set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
API_PREFIX="${API_PREFIX:-/api/v1}"
ENTITY_QUERY="${ENTITY_QUERY:-MINSA}"
COUNTRY="${COUNTRY:-pe}"
LOCALE="${LOCALE:-es}"
SSE_TIMEOUT_S="${SSE_TIMEOUT_S:-30}"
MIN_EVENTS="${MIN_EVENTS:-3}"

AUTH_HEADER=()
if [[ -n "${API_TOKEN:-}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${API_TOKEN}")
fi

log() {
  printf '[smoke-test] %s\n' "$*" >&2
}

cleanup() {
  if [[ -n "${SSE_PID:-}" ]] && kill -0 "${SSE_PID}" 2>/dev/null; then
    kill "${SSE_PID}" 2>/dev/null || true
    wait "${SSE_PID}" 2>/dev/null || true
  fi
  if [[ -n "${SSE_LOG:-}" && -f "${SSE_LOG}" ]]; then
    rm -f "${SSE_LOG}"
  fi
}
trap cleanup EXIT

# --- 1. POST /investigate -----------------------------------------------------
log "POST ${API_BASE}${API_PREFIX}/investigate (entity=${ENTITY_QUERY}, country=${COUNTRY})"
POST_BODY=$(printf '{"entity_query":"%s","country":"%s","locale":"%s"}' \
  "${ENTITY_QUERY}" "${COUNTRY}" "${LOCALE}")

POST_RESPONSE=$(curl -fsS -X POST \
  -H 'Content-Type: application/json' \
  "${AUTH_HEADER[@]}" \
  --data "${POST_BODY}" \
  "${API_BASE}${API_PREFIX}/investigate") || {
    log "POST failed"
    exit 1
  }

INVESTIGATION_ID=$(printf '%s' "${POST_RESPONSE}" \
  | sed -nE 's/.*"investigation_id"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p')

if [[ -z "${INVESTIGATION_ID}" ]]; then
  log "POST response had no investigation_id: ${POST_RESPONSE}"
  exit 1
fi
log "investigation_id=${INVESTIGATION_ID}"

# --- 2. Drain SSE stream ------------------------------------------------------
SSE_LOG=$(mktemp -t sabueso-sse.XXXXXX)
log "SSE GET ${API_BASE}${API_PREFIX}/stream/${INVESTIGATION_ID} (timeout=${SSE_TIMEOUT_S}s)"

# `curl -N` deshabilita buffer; `--max-time` corta a los SSE_TIMEOUT_S si el
# stream no se cierra solo. El backend cierra al emitir un terminal event
# (investigation_complete / investigation_failed), así que normalmente curl
# vuelve mucho antes del timeout.
curl -N -sS --max-time "${SSE_TIMEOUT_S}" \
  -H 'Accept: text/event-stream' \
  "${AUTH_HEADER[@]}" \
  "${API_BASE}${API_PREFIX}/stream/${INVESTIGATION_ID}" >"${SSE_LOG}" 2>/dev/null &
SSE_PID=$!

wait "${SSE_PID}" 2>/dev/null || true
SSE_PID=""

EVENT_COUNT=$(grep -c -E '^event:' "${SSE_LOG}" 2>/dev/null || true)
EVENT_COUNT=${EVENT_COUNT:-0}
log "SSE event count: ${EVENT_COUNT}"

if [[ "${EVENT_COUNT}" -lt "${MIN_EVENTS}" ]]; then
  log "SSE delivered ${EVENT_COUNT} events, expected ≥${MIN_EVENTS}"
  log "--- sse tail ---"
  tail -n 40 "${SSE_LOG}" >&2 || true
  exit 2
fi

# --- 3. GET /investigations/{id} ---------------------------------------------
log "GET ${API_BASE}${API_PREFIX}/investigations/${INVESTIGATION_ID}"
GET_RESPONSE=$(curl -fsS \
  "${AUTH_HEADER[@]}" \
  "${API_BASE}${API_PREFIX}/investigations/${INVESTIGATION_ID}")

STATUS=$(printf '%s' "${GET_RESPONSE}" \
  | sed -nE 's/.*"status"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p')

log "investigation.status=${STATUS}"

if [[ "${STATUS}" != "complete" ]]; then
  log "expected status=complete, got status=${STATUS}"
  log "GET response: ${GET_RESPONSE}"
  exit 3
fi

log "OK · ${EVENT_COUNT} SSE events · status=${STATUS}"
exit 0
