#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-${FANTASY_PI_BACKUP_DIR:-/var/backups/fantasy-football-pi}}"
STALE_HOURS="${STALE_HOURS:-25}"
ALERT_EMAIL="${ALERT_EMAIL:-}"

if [[ ! -d "${BACKUP_DIR}" ]]; then
  echo "ERROR: backup directory not found: ${BACKUP_DIR}" >&2
  exit 2
fi

latest_backup="$(find "${BACKUP_DIR}" -type f \( -name '*.dump.gz' -o -name '*.sqlite.gz' -o -name '*.dump' -o -name '*.sqlite' \) -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2- || true)"

if [[ -z "${latest_backup}" ]]; then
  echo "ERROR: no backup files found in ${BACKUP_DIR}" >&2
  if [[ -n "${ALERT_EMAIL}" ]]; then
    printf 'No successful database backup found in %s in the last %s hours.\n' "${BACKUP_DIR}" "${STALE_HOURS}" | mail -s "Fantasy Football Pi backup alert" "${ALERT_EMAIL}"
  fi
  exit 3
fi

latest_epoch="$(stat -c %Y "${latest_backup}")"
now_epoch="$(date +%s)"
age_hours=$(( (now_epoch - latest_epoch) / 3600 ))

if (( age_hours > STALE_HOURS )); then
  echo "ERROR: latest backup is stale (${age_hours} hours old): ${latest_backup}" >&2
  if [[ -n "${ALERT_EMAIL}" ]]; then
    printf 'Latest database backup is stale: %s (%s hours old).\n' "${latest_backup}" "${age_hours}" | mail -s "Fantasy Football Pi backup alert" "${ALERT_EMAIL}"
  fi
  exit 4
fi

echo "OK: latest backup is ${age_hours} hours old (${latest_backup})"
