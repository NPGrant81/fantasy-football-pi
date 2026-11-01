# Restore Runbook (microSD backups)

Created: 2026-03-10
Last reviewed: 2026-10-31
Related Issue: #216

## Scope
This runbook restores the Fantasy Football Pi database from backups created by `ops/backup/microsd_db_backup.sh`.

## Preconditions
- microSD mounted at `/mnt/microsd`
- backup files exist under `/mnt/microsd/backups/fantasy-football-pi`
- the backend service is stopped before restore; PostgreSQL remains available

## 1. Locate backup artifact
```bash
ls -lah /mnt/microsd/backups/fantasy-football-pi
```

## 2. Restore PostgreSQL (custom dump)
Stop API/service first, then:
```bash
LATEST=$(ls -1t /mnt/microsd/backups/fantasy-football-pi/postgres_*.dump.gz | head -n 1)
gunzip -c "$LATEST" > /tmp/restore.dump

# Example target DB URL
export DATABASE_URL="postgresql://postgres:password@127.0.0.1:5432/fantasy_pi"

# This replaces objects in the selected database. Verify DATABASE_URL and the
# backup artifact before running the restore.
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" /tmp/restore.dump
rm -f /tmp/restore.dump
```

## 3. Restore SQLite backup
```bash
LATEST=$(ls -1t /mnt/microsd/backups/fantasy-football-pi/sqlite_*.sqlite.gz | head -n 1)
gunzip -c "$LATEST" > /tmp/restore.sqlite

# Replace the target database file only after stopping every process that uses it.
cp /tmp/restore.sqlite /path/to/target.db
rm -f /tmp/restore.sqlite
```

## 4. Validate restored database before starting the API
```bash
# Verify key tables are populated (Postgres example)
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM users;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM league_settings;"
```

## 5. Validate recovery without touching live data

The repository recovery check creates a fresh backup using the generic
`scripts/backup_db.sh` workflow and validates restoration into an isolated
database. It does not exercise the Pi microSD systemd timer or validate an
existing microSD backup artifact:

```bash
DB_URL="sqlite:////var/lib/fantasy-football-pi/app.db" \
BACKUP_DIR="/var/backups/fantasy-football-pi" \
./scripts/validate_backup_recovery.sh
```

This script:
- creates a fresh backup snapshot
- checks the newest backup is within the stale threshold
- runs `restore_db.sh --dry-run` against the generated backup
- exits non-zero if any step fails

Run this check as one input before a production restore drill; separately
verify that the scheduled microSD unit succeeds and inspect the backup artifact
you intend to restore.

## 6. Restart services
```bash
sudo systemctl start fantasy-football-backend
sudo systemctl status fantasy-football-backend --no-pager
curl -fsS http://127.0.0.1:8000/health
```

## Automation setup (timer)
```bash
sudo mkdir -p /opt/fantasy-football-pi/ops/backup
sudo install -m 0755 ops/backup/microsd_db_backup.sh /opt/fantasy-football-pi/ops/backup/microsd_db_backup.sh
sudo cp deploy/systemd/microsd-db-backup.service.example /etc/systemd/system/microsd-db-backup.service
sudo cp deploy/systemd/microsd-db-backup.timer.example /etc/systemd/system/microsd-db-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now microsd-db-backup.timer
sudo systemctl status microsd-db-backup.timer --no-pager
```

## Acceptance test checklist
- timer runs daily and writes `.gz` backup files to microSD
- retention deletes old backups beyond configured days
- restore command succeeds in dev/staging environment
- `/health` returns `200` after restore
