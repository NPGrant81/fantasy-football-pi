#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DB_URL="${DB_URL:-${DATABASE_URL:-}}"
BACKUP_DIR="${BACKUP_DIR:-${FANTASY_PI_BACKUP_DIR:-/var/backups/fantasy-football-pi}}"
STALE_HOURS="${STALE_HOURS:-25}"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  # shellcheck disable=SC1090
  source "${REPO_ROOT}/.env"
  DB_URL="${DB_URL:-${DATABASE_URL:-}}"
fi

if [[ -z "${DB_URL}" ]]; then
  echo "Error: DB_URL or DATABASE_URL must be set before running validate_backup_recovery.sh" >&2
  exit 1
fi

redact_db_url() {
  local value="${1}"
  if [[ "${value}" =~ ^([^:]+://)([^@]+)@ ]]; then
    echo "${BASH_REMATCH[1]}***@${value#*@}"
  else
    echo "${value}"
  fi
}

mkdir -p "${BACKUP_DIR}"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

log "Starting backup recovery validation"
log "Backup directory: ${BACKUP_DIR}"
log "Database URL: $(redact_db_url "${DB_URL}")"

BACKUP_DIR="${BACKUP_DIR}" DB_URL="${DB_URL}" bash "${REPO_ROOT}/scripts/backup_db.sh"

latest_backup="$(find "${BACKUP_DIR}" -type f \( -name '*.dump.gz' -o -name '*.sqlite.gz' -o -name '*.dump' -o -name '*.sqlite' \) -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2- || true)"
if [[ -z "${latest_backup}" ]]; then
  echo "Error: no backup file was created in ${BACKUP_DIR}" >&2
  exit 2
fi

log "Newest backup available: ${latest_backup}"
BACKUP_DIR="${BACKUP_DIR}" STALE_HOURS="${STALE_HOURS}" bash "${REPO_ROOT}/scripts/check_backup_status.sh"
BACKUP_DIR="${BACKUP_DIR}" DB_URL="${DB_URL}" bash "${REPO_ROOT}/scripts/restore_db.sh" --dry-run "${latest_backup}"

log "Recovery validation passed: backup creation, freshness check, and dry-run restore all succeeded"
