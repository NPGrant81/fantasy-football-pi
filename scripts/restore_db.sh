#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DB_URL="${DB_URL:-${DATABASE_URL:-}}"
BACKUP_DIR="${BACKUP_DIR:-${FANTASY_PI_BACKUP_DIR:-${HOME}/.local/share/fantasy-football-pi/backups}}"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: restore_db.sh [--dry-run] [--backup-dir DIR] [--db-url URL] [BACKUP_FILE]

If BACKUP_FILE is omitted, the newest matching backup in BACKUP_DIR is used.
Supported backup extensions:
  - .dump.gz / .dump (PostgreSQL)
  - .sqlite.gz / .sqlite (SQLite)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --backup-dir)
      BACKUP_DIR="$2"
      shift 2
      ;;
    --db-url)
      DB_URL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

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
  echo "Error: DB_URL or DATABASE_URL must be set before running restore_db.sh" >&2
  exit 1
fi

if [[ $# -gt 0 ]]; then
  ARCHIVE_PATH="$1"
else
  ARCHIVE_PATH="$(ls -1t "${BACKUP_DIR}"/*.dump.gz "${BACKUP_DIR}"/*.sqlite.gz "${BACKUP_DIR}"/*.dump "${BACKUP_DIR}"/*.sqlite 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "${ARCHIVE_PATH}" || ! -f "${ARCHIVE_PATH}" ]]; then
  echo "Error: no backup archive found in ${BACKUP_DIR}. Supply a path explicitly." >&2
  exit 1
fi

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

CLEANUP_TMP=""
cleanup() {
  if [[ -n "${CLEANUP_TMP}" && -f "${CLEANUP_TMP}" ]]; then
    rm -f "${CLEANUP_TMP}"
  fi
}
trap cleanup EXIT

if [[ "${DB_URL}" =~ ^postgres(ql)?:// ]]; then
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "Dry run: would restore Postgres backup from ${ARCHIVE_PATH}"
    exit 0
  fi

  TARGET_PATH="${ARCHIVE_PATH}"
  if [[ "${ARCHIVE_PATH}" == *.gz ]]; then
    TMP_FILE="$(mktemp /tmp/fantasy-pi-restore.XXXXXX.dump)"
    gzip -dc "${ARCHIVE_PATH}" > "${TMP_FILE}"
    TARGET_PATH="${TMP_FILE}"
    CLEANUP_TMP="${TMP_FILE}"
  fi

  command -v pg_restore >/dev/null 2>&1 || { echo "Error: pg_restore not found in PATH" >&2; exit 1; }
  log "Restoring PostgreSQL backup from ${ARCHIVE_PATH}"
  pg_restore --clean --if-exists --no-owner --no-privileges --dbname="${DB_URL}" "${TARGET_PATH}"
  log "PostgreSQL restore complete"
elif [[ "${DB_URL}" =~ ^sqlite://(/|.*)$ ]]; then
  DB_PATH="${DB_URL#sqlite:///}"
  if [[ "${DB_PATH}" == "${DB_URL}" ]]; then
    DB_PATH="${DB_URL#sqlite://}"
  fi
  if [[ "${DB_PATH}" != /* && -d "${REPO_ROOT}" ]]; then
    DB_PATH="${REPO_ROOT}/${DB_PATH}"
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "Dry run: would restore SQLite backup ${ARCHIVE_PATH} to ${DB_PATH}"
    exit 0
  fi

  TARGET_PATH="${ARCHIVE_PATH}"
  if [[ "${ARCHIVE_PATH}" == *.gz ]]; then
    TMP_FILE="$(mktemp /tmp/fantasy-pi-restore.XXXXXX.sqlite)"
    gzip -dc "${ARCHIVE_PATH}" > "${TMP_FILE}"
    TARGET_PATH="${TMP_FILE}"
    CLEANUP_TMP="${TMP_FILE}"
  fi

  mkdir -p "$(dirname "${DB_PATH}")"
  cp "${TARGET_PATH}" "${DB_PATH}"
  log "SQLite restore complete -> ${DB_PATH}"
else
  echo "Error: Unsupported database URL scheme" >&2
  exit 1
fi
