#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_HEALTH_URL="http://${BACKEND_HOST}:${BACKEND_PORT}/health"
BACKEND_LOG="${ROOT_DIR}/.dev-backend.log"

BACKEND_PID=""

log() {
  printf "[%s] %s\n" "$(date +"%H:%M:%S")" "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

cleanup() {
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    log "Stopping backend (PID ${BACKEND_PID})"
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

require_cmd curl
require_cmd python
require_cmd npm
require_cmd ss

cd "${ROOT_DIR}"

if [[ ! -d "frontend" ]]; then
  log "frontend directory not found. Run this script from the repository root."
  exit 1
fi

if [[ ! -f "backend/.env" ]]; then
  log "backend/.env not found. Creating it from backend/.env.example."
  cp backend/.env.example backend/.env
fi

if command -v pg_isready >/dev/null 2>&1; then
  if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    log "Postgres is reachable on 127.0.0.1:5432"
  else
    log "Postgres is not reachable on 127.0.0.1:5432 (continuing; backend may fail if DB is required)."
  fi
else
  log "pg_isready not found; skipping Postgres readiness check."
fi

if curl -fsS "${BACKEND_HEALTH_URL}" >/dev/null 2>&1; then
  log "Backend already healthy at ${BACKEND_HEALTH_URL}"
else
  if ss -ltn | grep -q ":${BACKEND_PORT} "; then
    log "Port ${BACKEND_PORT} is already in use, but ${BACKEND_HEALTH_URL} is not healthy."
    log "Stop the process using port ${BACKEND_PORT} or set BACKEND_PORT to a different value."
    exit 1
  fi

  log "Starting backend on ${BACKEND_HOST}:${BACKEND_PORT}"
  python -m uvicorn backend.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" --reload >"${BACKEND_LOG}" 2>&1 &
  BACKEND_PID="$!"
  log "Backend PID: ${BACKEND_PID} (logs: ${BACKEND_LOG})"

  for i in $(seq 1 60); do
    if curl -fsS "${BACKEND_HEALTH_URL}" >/dev/null 2>&1; then
      log "Backend is healthy"
      break
    fi

    if ! kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
      log "Backend exited before becoming healthy. Last log lines:"
      tail -n 40 "${BACKEND_LOG}" || true
      exit 1
    fi

    sleep 1

    if [[ "${i}" -eq 60 ]]; then
      log "Timed out waiting for backend health at ${BACKEND_HEALTH_URL}"
      tail -n 40 "${BACKEND_LOG}" || true
      exit 1
    fi
  done
fi

log "Starting frontend on port ${FRONTEND_PORT}"
cd "${ROOT_DIR}/frontend"
exec npm run dev -- --port "${FRONTEND_PORT}" --strictPort
