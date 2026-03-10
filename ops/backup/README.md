# Backup Scripts

This folder contains backup automation scripts.

## microSD backup script
- Script: `microsd_db_backup.sh`
- Purpose: write low-frequency compressed DB backups to microSD storage
- Supports:
  - PostgreSQL via `pg_dump --format=custom`
  - SQLite via `sqlite3 .backup`
- Retention: deletes backups older than `RETENTION_DAYS` (default `14`)

## Required environment
- `BACKUP_MOUNT` (default: `/mnt/microsd`)
- `BACKUP_SUBDIR` (default: `backups/fantasy-football-pi`)
- `RETENTION_DAYS` (default: `14`)
- `DB_URL` or `DATABASE_URL`

## Manual run
```bash
bash ops/backup/microsd_db_backup.sh
```

## Automated run (systemd)
Use:
- `deploy/systemd/microsd-db-backup.service.example`
- `deploy/systemd/microsd-db-backup.timer.example`
