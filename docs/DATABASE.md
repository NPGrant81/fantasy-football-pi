# Database Strategy and Backup Runbook

## Decision summary

The project currently uses SQLite in local development and CI because it is simple and fast for single-developer workflows. For Raspberry Pi production use, PostgreSQL is the recommended default for the runtime database because it has stronger durability, clearer backup/restore tooling, and better operational behavior when multiple processes or background jobs are active.

This repo keeps SQLite compatibility for local testing and simple deployments, but production operations should prefer PostgreSQL with a persistent named volume and scheduled backups.

## Production volume layout

Recommended runtime layout for the Pi:

- database data directory: `/var/lib/fantasy-football-pi/postgres`
- backup directory: `/var/backups/fantasy-football-pi`
- application DB URL: set via `DATABASE_URL` or `DB_URL`

If the app is run via Docker Compose or a container stack, mount a named volume such as:

- volume name: `fantasy_pi_postgres_data`
- container mount: `/var/lib/postgresql/data`

This keeps database data alive across container restarts and allows a clean backup/restore cycle without relying on ephemeral container storage.

## Backup workflow

The repo provides two helper scripts:

- `scripts/backup_db.sh`
- `scripts/restore_db.sh`

### Create a backup

```bash
DB_URL="postgresql://postgres@127.0.0.1:5432/fantasy_pi" \
BACKUP_DIR="/var/backups/fantasy-football-pi" \
./scripts/backup_db.sh
```

For SQLite:

```bash
DB_URL="sqlite:////var/lib/fantasy-football-pi/app.db" \
BACKUP_DIR="/var/backups/fantasy-football-pi" \
./scripts/backup_db.sh
```

The script writes timestamped snapshots like:

- `postgres_20260829T000000Z.dump.gz`
- `sqlite_20260829T000000Z.sqlite.gz`

and prunes backups older than the configured retention window (default: 7 days).

### Restore a backup

```bash
DB_URL="postgresql://postgres@127.0.0.1:5432/fantasy_pi" \
BACKUP_DIR="/var/backups/fantasy-football-pi" \
./scripts/restore_db.sh /var/backups/fantasy-football-pi/postgres_20260829T000000Z.dump.gz
```

Dry run:

```bash
DB_URL="postgresql://postgres@127.0.0.1:5432/fantasy_pi" \
./scripts/restore_db.sh --dry-run /var/backups/fantasy-football-pi/postgres_20260829T000000Z.dump.gz
```

### Restore with the newest local backup

```bash
DB_URL="sqlite:////var/lib/fantasy-football-pi/app.db" \
BACKUP_DIR="/var/backups/fantasy-football-pi" \
./scripts/restore_db.sh
```

## Pi automation

On the Raspberry Pi, schedule nightly backup execution with cron or a systemd timer. A minimal cron example:

```cron
0 2 * * * /home/pi/fantasy-football-pi/scripts/backup_db.sh >> /var/log/fantasy-football-pi-backups.log 2>&1
```

Operational guardrail:

- ensure the backup directory is writable
- ensure the database service is healthy before backup begins
- keep at least 7 local snapshots online
- copy the newest snapshot to an off-device target nightly

## Off-device backup

Recommended destinations:

- OneDrive via rclone
- Backblaze B2
- S3-compatible object storage

Example rclone sync:

```bash
rclone sync /var/backups/fantasy-football-pi remote:fantasy-football-pi-backups
```

This keeps a second copy outside the Pi in case the SD card fails or the device is replaced.

## Monitoring and alerting

If a backup has not succeeded in the last 25 hours, the system should produce an alert or incident note. The repo includes `scripts/check_backup_status.sh`, which inspects the latest backup timestamp in the configured `BACKUP_DIR` and exits non-zero when the newest snapshot is older than the configured `STALE_HOURS` threshold.

Example cron entry:

```cron
0 * * * * /home/pi/fantasy-football-pi/scripts/check_backup_status.sh >> /var/log/fantasy-football-pi-check-backup.log 2>&1
```

This keeps backup freshness visible and surfaces a failure before a missing backup becomes a production incident.

## Restore checklist

- stop the application or backend service before restore
- ensure the target database is reachable and writable
- confirm the backup file is the correct environment snapshot
- run the restore command
- validate `/health` and key table counts
- restart the backend service

## Safety notes

- never expose production `DATABASE_URL` values in git or logs
- keep copies of credentials in secret storage, not committed files
- prefer Postgres for production workloads even when local development remains SQLite
- test restore flow from a real backup artifact before depending on it in production
