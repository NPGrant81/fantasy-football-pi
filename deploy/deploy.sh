#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APP_SERVICE="${APP_SERVICE:-fantasy-football-backend}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
ROLLBACK_REF_FILE="${ROLLBACK_REF_FILE:-${REPO_ROOT}/.deploy-last-good}"
BACKUP_SCRIPT="${BACKUP_SCRIPT:-${REPO_ROOT}/ops/backup/microsd_db_backup.sh}"

log() {
  printf '\n[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

fail() {
  printf '\n[%s] ERROR: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

wait_for_health() {
  local attempts=0
  local max_attempts=${WAIT_FOR_HEALTH_ATTEMPTS:-30}
  local delay_seconds=${WAIT_FOR_HEALTH_DELAY_SECONDS:-2}

  while (( attempts < max_attempts )); do
    if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
      log "Health check passed at ${HEALTH_URL}"
      return 0
    fi
    attempts=$((attempts + 1))
    sleep "${delay_seconds}"
  done

  fail "Application did not become healthy within ${max_attempts} attempts at ${HEALTH_URL}"
}

record_rollback_ref() {
  if git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "${REPO_ROOT}" rev-parse HEAD > "${ROLLBACK_REF_FILE}"
    log "Recorded rollback ref: $(cat "${ROLLBACK_REF_FILE}")"
  fi
}

run_deploy() {
  require_command git
  require_command curl
  require_command systemctl

  if [[ ! -d "${REPO_ROOT}" ]]; then
    fail "Repository root not found: ${REPO_ROOT}"
  fi

  record_rollback_ref

  log "Pulling latest repository changes"
  git -C "${REPO_ROOT}" pull --ff-only

  if [[ -f "${REPO_ROOT}/backend/apply_migrations.py" ]]; then
    log "Applying migrations"
    (cd "${REPO_ROOT}" && python3 -m backend.apply_migrations)
  fi

  if [[ -d "${REPO_ROOT}/frontend" ]]; then
    log "Ensuring frontend dependencies are present"
    (cd "${REPO_ROOT}/frontend" && if [[ -d node_modules ]]; then npm install --no-fund --no-audit >/dev/null; else npm ci --no-fund --no-audit >/dev/null; fi)
  fi

  log "Restarting ${APP_SERVICE}"
  systemctl daemon-reload
  systemctl restart "${APP_SERVICE}"

  wait_for_health
  log "Deploy completed successfully"
}

run_rollback() {
  require_command git
  require_command systemctl

  if [[ ! -f "${ROLLBACK_REF_FILE}" ]]; then
    fail "No rollback ref recorded. Nothing to revert to."
  fi

  local previous_ref
  previous_ref="$(cat "${ROLLBACK_REF_FILE}")"
  log "Rolling back to ${previous_ref}"
  git -C "${REPO_ROOT}" checkout "${previous_ref}"

  if [[ -f "${REPO_ROOT}/backend/apply_migrations.py" ]]; then
    log "Applying migrations for rollback"
    (cd "${REPO_ROOT}" && python3 -m backend.apply_migrations)
  fi

  systemctl restart "${APP_SERVICE}"
  wait_for_health
  log "Rollback completed successfully"
}

run_restart() {
  require_command systemctl
  log "Restarting ${APP_SERVICE}"
  systemctl restart "${APP_SERVICE}"
  wait_for_health
}

run_logs() {
  require_command journalctl
  journalctl -u "${APP_SERVICE}" -f -n 100
}

run_status() {
  printf '\n== service ==\n'
  systemctl is-active --quiet "${APP_SERVICE}" && echo "ACTIVE" || echo "INACTIVE"
  printf '\n== health ==\n'
  if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
    curl -fsS "${HEALTH_URL}"
  else
    echo "unhealthy: ${HEALTH_URL}"
  fi
  printf '\n== disk ==\n'
  df -h /
}

run_backup() {
  if [[ -x "${BACKUP_SCRIPT}" ]]; then
    log "Running backup script ${BACKUP_SCRIPT}"
    bash "${BACKUP_SCRIPT}"
  else
    fail "Backup script not found or not executable: ${BACKUP_SCRIPT}"
  fi
}

run_restore() {
  local archive_path="${1:-}"
  if [[ -z "${archive_path}" ]]; then
    fail "Usage: deploy.sh restore <backup-archive>"
  fi

  if [[ ! -f "${archive_path}" ]]; then
    fail "Backup archive not found: ${archive_path}"
  fi

  log "Restore requested for ${archive_path}"
  if [[ "${archive_path}" == *.gz ]]; then
    gzip -dc "${archive_path}" | tar -xvf - -C "${REPO_ROOT}"
  else
    cp "${archive_path}" "${REPO_ROOT}/restore/$(basename "${archive_path}")"
  fi

  log "Restore command completed. Validate with systemctl status ${APP_SERVICE}"
}

usage() {
  cat <<EOF
Usage: deploy.sh <command>

Commands:
  deploy             pull latest changes, apply migrations, restart service, verify /health
  rollback           restore the last recorded healthy commit and restart the service
  restart            restart the backend only
  logs              tail the backend journald logs
  status            print service status and current health payload
  backup            run the configured database backup script
  restore <file>     restore an archive into the repo root (or use your backup workflow)
  help              show this help
EOF
}

cmd="${1:-help}"
case "${cmd}" in
  deploy) run_deploy ;;
  rollback) run_rollback ;;
  restart) run_restart ;;
  logs) run_logs ;;
  status) run_status ;;
  backup) run_backup ;;
  restore) shift; run_restore "$*" ;;
  help|-h|--help) usage ;;
  *) echo "Unknown command: ${cmd}" >&2; usage >&2; exit 1 ;;
 esac
