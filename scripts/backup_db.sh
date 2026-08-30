#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-${FANTASY_PI_BACKUP_DIR:-${HOME}/.local/share/fantasy-football-pi/backups}}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DB_URL="${DB_URL:-${DATABASE_URL:-}}"

if [[ -z "${DB_URL}" && -f "${REPO_ROOT}/backend/.env" ]]; then
  # shellcheck disable=SC1090
  source "${REPO_ROOT}/backend/.env"
  DB_URL="${DB_URL:-${DATABASE_URL:-}}"
fi

if [[ -z "${DB_URL}" && -f "${REPO_ROOT}/.env" ]]; then
  # shellcheck disable=SC1090
  source "${REPO_ROOT}/.env"
  DB_URL="${DB_URL:-${DATABASE_URL:-}}"
fi

if [[ -z "${DB_URL}" ]]; then
  echo "Error: DB_URL or DATABASE_URL must be set before running backup_db.sh" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

if [[ "${DB_URL}" =~ ^postgres(ql)?:// ]]; then
  OUT_FILE="${BACKUP_DIR}/postgres_${TIMESTAMP}.dump"
  log "Starting Postgres backup -> ${OUT_FILE}"
  command -v pg_dump >/dev/null 2>&1 || { echo "Error: pg_dump not found in PATH" >&2; exit 1; }
  pg_dump --format=custom --file="${OUT_FILE}" "${DB_URL}"
  gzip -f "${OUT_FILE}"
  log "Postgres backup completed -> ${OUT_FILE}.gz"
elif [[ "${DB_URL}" =~ ^sqlite://(/|.*)$ ]]; then
  DB_PATH="${DB_URL#sqlite:///}"
  if [[ "${DB_PATH}" == "${DB_URL}" ]]; then
    DB_PATH="${DB_URL#sqlite://}"
  fi
  if [[ "${DB_PATH}" != /* && -f "${REPO_ROOT}/${DB_PATH}" ]]; then
    DB_PATH="${REPO_ROOT}/${DB_PATH}"
  fi
  if [[ -z "${DB_PATH}" ]]; then
    echo "Error: SQLite URL did not include a database path" >&2
    exit 1
  fi
  if [[ ! -f "${DB_PATH}" ]]; then
    echo "Error: SQLite database not found: ${DB_PATH}" >&2
    exit 1
  fi
  command -v sqlite3 >/dev/null 2>&1 || { echo "Error: sqlite3 not found in PATH" >&2; exit 1; }
  OUT_FILE="${BACKUP_DIR}/sqlite_${TIMESTAMP}.sqlite"
  log "Starting SQLite backup -> ${OUT_FILE}"
  sqlite3 "${DB_PATH}" ".backup '${OUT_FILE}'"
  gzip -f "${OUT_FILE}"
  log "SQLite backup completed -> ${OUT_FILE}.gz"
else
  echo "Error: Unsupported database URL scheme" >&2
  exit 1
fi

find "${BACKUP_DIR}" -type f \( -name '*.dump.gz' -o -name '*.sqlite.gz' \) -mtime "+${RETENTION_DAYS}" -delete
log "Backup retention pruned to ${RETENTION_DAYS} days"
log "Backup succeeded"
