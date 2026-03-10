#!/usr/bin/env bash
set -euo pipefail

# Create daily database backups on microSD with retention.
# Supports Postgres (pg_dump) and SQLite (.backup).
#
# Environment overrides:
#   BACKUP_MOUNT=/mnt/microsd
#   BACKUP_SUBDIR=backups/fantasy-football-pi
#   RETENTION_DAYS=14
#   DB_URL=postgresql://...
#
# Usage:
#   bash ops/backup/microsd_db_backup.sh

BACKUP_MOUNT="${BACKUP_MOUNT:-/mnt/microsd}"
BACKUP_SUBDIR="${BACKUP_SUBDIR:-backups/fantasy-football-pi}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  # shellcheck disable=SC1090
  source "${REPO_ROOT}/.env"
fi

DB_URL="${DB_URL:-${DATABASE_URL:-}}"
BACKUP_DIR="${BACKUP_MOUNT}/${BACKUP_SUBDIR}"
TIMESTAMP="$(date +%F_%H%M%S)"
LOG_PREFIX="[$(date -Is)]"

log() {
  printf '%s %s\n' "${LOG_PREFIX}" "$*"
}

fail() {
  printf '%s ERROR: %s\n' "${LOG_PREFIX}" "$*" >&2
  exit 1
}

[[ -d "${BACKUP_MOUNT}" ]] || fail "Backup mount path not found: ${BACKUP_MOUNT}"
[[ -w "${BACKUP_MOUNT}" ]] || fail "Backup mount path is not writable: ${BACKUP_MOUNT}"
mkdir -p "${BACKUP_DIR}"

if [[ -z "${DB_URL}" ]]; then
  fail "No DB URL found. Set DB_URL or DATABASE_URL."
fi

if [[ "${DB_URL}" =~ ^postgres(ql)?:// ]]; then
  command -v pg_dump >/dev/null 2>&1 || fail "pg_dump not found in PATH"
  OUT_FILE="${BACKUP_DIR}/postgres_${TIMESTAMP}.dump"
  log "Starting Postgres backup -> ${OUT_FILE}"
  pg_dump --format=custom --file="${OUT_FILE}" "${DB_URL}"
  gzip -f "${OUT_FILE}"
  log "Postgres backup completed -> ${OUT_FILE}.gz"
elif [[ "${DB_URL}" =~ ^sqlite:///(.+)$ ]]; then
  DB_PATH="/${BASH_REMATCH[1]}"
  [[ -f "${DB_PATH}" ]] || fail "SQLite DB path not found: ${DB_PATH}"
  command -v sqlite3 >/dev/null 2>&1 || fail "sqlite3 not found in PATH"
  OUT_FILE="${BACKUP_DIR}/sqlite_${TIMESTAMP}.sqlite"
  log "Starting SQLite backup -> ${OUT_FILE}"
  sqlite3 "${DB_PATH}" ".backup '${OUT_FILE}'"
  gzip -f "${OUT_FILE}"
  log "SQLite backup completed -> ${OUT_FILE}.gz"
else
  fail "Unsupported DB URL scheme in '${DB_URL}'"
fi

log "Applying retention: delete backups older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}" -type f \( -name '*.dump.gz' -o -name '*.sqlite.gz' \) -mtime "+${RETENTION_DAYS}" -delete

log "Backup run completed successfully"
