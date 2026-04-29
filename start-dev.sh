#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
# Always probe 127.0.0.1 so the health check works even when BACKEND_HOST is 0.0.0.0
BACKEND_HEALTH_HOST="${BACKEND_HEALTH_HOST:-127.0.0.1}"
BACKEND_HEALTH_URL="http://${BACKEND_HEALTH_HOST}:${BACKEND_PORT}/health"
BACKEND_LOG="${ROOT_DIR}/.dev-backend.log"
BACKEND_PYTHON=""

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

resolve_backend_python() {
  local candidates=(
    "${ROOT_DIR}/backend/venv/bin/python3"
    "${ROOT_DIR}/backend/venv/bin/python"
    "${ROOT_DIR}/.venv/bin/python3"
    "${ROOT_DIR}/.venv/bin/python"
  )

  for py in "${candidates[@]}"; do
    if [[ -x "${py}" ]] && "${py}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
      BACKEND_PYTHON="${py}"
      return 0
    fi
  done

  for py in python3 python; do
    if command -v "${py}" >/dev/null 2>&1 && "${py}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
      BACKEND_PYTHON="${py}"
      return 0
    fi
  done

  log "Could not find a Python interpreter with fastapi and uvicorn installed."
  log "Install backend dependencies in backend/venv (or activate the venv), then retry."
  exit 1
}

port_in_use() {
  local port="$1"

  if command -v ss >/dev/null 2>&1; then
    ss -ltn | grep -q ":${port} "
    return $?
  fi

  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi

  log "Could not find a supported port-inspection tool (ss or lsof)."
  log "Install one of them or set BACKEND_PORT/FRONTEND_PORT to known-free ports."
  exit 1
}

kill_port() {
  local port="$1"
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti TCP:"${port}" 2>/dev/null || true)"
  elif command -v ss >/dev/null 2>&1; then
    pids="$(ss -ltnp "sport = :${port}" 2>/dev/null | awk -F'pid=' '/pid=/{gsub(/,.*/,"",$2); print $2}' || true)"
  fi

  if [[ -n "${pids}" ]]; then
    log "Killing stale process(es) on port ${port}: ${pids}"
    echo "${pids}" | xargs kill -9 2>/dev/null || true
    sleep 1
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
require_cmd npm

cd "${ROOT_DIR}"

if [[ ! -d "frontend" ]]; then
  log "frontend directory not found. Run this script from the repository root."
  exit 1
fi

if [[ ! -f "backend/.env" ]]; then
  if [[ ! -f "backend/.env.example" ]]; then
    log "backend/.env.example not found. Cannot bootstrap backend/.env."
    exit 1
  fi
  log "backend/.env not found. Creating it from backend/.env.example."
  cp backend/.env.example backend/.env
fi

resolve_backend_python
if [[ -z "${BACKEND_PYTHON}" ]]; then
  log "Could not find a Python interpreter with fastapi and uvicorn installed."
  log "Install backend dependencies in backend/venv (or activate the venv), then retry."
  exit 1
fi
log "Using backend Python: ${BACKEND_PYTHON}"

if port_in_use "${FRONTEND_PORT}"; then
  log "Frontend port ${FRONTEND_PORT} is already in use — killing stale process."
  kill_port "${FRONTEND_PORT}"
fi

if command -v pg_isready >/dev/null 2>&1; then
  if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    log "Postgres is reachable on 127.0.0.1:5432"
  else
    log "Postgres is not reachable on 127.0.0.1:5432."
    log "Backend health requires DB connectivity, so startup will likely fail until Postgres is available."
  fi
else
  log "pg_isready not found; skipping Postgres readiness check."
fi

if curl -fsS "${BACKEND_HEALTH_URL}" >/dev/null 2>&1; then
  log "Backend already healthy at ${BACKEND_HEALTH_URL}"
else
  if port_in_use "${BACKEND_PORT}"; then
    log "Port ${BACKEND_PORT} is already in use but not healthy — killing stale process."
    kill_port "${BACKEND_PORT}"
  fi

  log "Starting backend on ${BACKEND_HOST}:${BACKEND_PORT}"
  "${BACKEND_PYTHON}" -m uvicorn backend.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" --reload >"${BACKEND_LOG}" 2>&1 &
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
npm run dev -- --port "${FRONTEND_PORT}" --strictPort
