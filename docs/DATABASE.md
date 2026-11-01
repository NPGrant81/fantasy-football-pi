# Database Strategy and Backup Runbook

## Decision summary

The project currently uses SQLite in local development and CI because it is simple and fast for single-developer workflows. For Raspberry Pi production use, PostgreSQL is the recommended default for the runtime database because it has stronger durability, clearer backup/restore tooling, and better operational behavior when multiple processes or background jobs are active.

This repo keeps SQLite compatibility for local testing and simple deployments,
but production operations should prefer PostgreSQL on persistent storage with
scheduled backups. The current Pi deployment uses native PostgreSQL; use a
persistent named volume only when running the database in a container.

## Production volume layout

Recommended runtime layout for the Pi:

- database data directory: `/var/lib/fantasy-football-pi/postgres`
- scheduled microSD backup directory: `/mnt/microsd/backups/fantasy-football-pi`
- application DB URL: set via `DATABASE_URL` or `DB_URL`

The generic repository backup scripts use `BACKUP_DIR` (defaulting to a
user-local backup directory). The Raspberry Pi systemd timer uses the dedicated
microSD backup script and the path above; these workflows have separate
retention settings.

If the app is run via Docker Compose or a container stack, mount a named volume such as:

- volume name: `fantasy_pi_postgres_data`
- container mount: `/var/lib/postgresql/data`

For containerized deployments, this keeps database data alive across container
restarts and avoids relying on ephemeral container storage.

## Backup workflow

The repo provides generic backup/restore scripts and a separate Pi microSD
backup script:

- `scripts/backup_db.sh`
- `scripts/restore_db.sh`

### Create a backup

```bash
DB_URL="<database URL from a protected environment source>" \
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
Do not put a production database URL containing credentials directly in shell
history; provide it through the approved protected environment source.

### Restore a backup

```bash
DB_URL="<database URL from a protected environment source>" \
BACKUP_DIR="/var/backups/fantasy-football-pi" \
./scripts/restore_db.sh /var/backups/fantasy-football-pi/postgres_20260829T000000Z.dump.gz
```

PostgreSQL restore uses `pg_restore --clean --if-exists`, which replaces
objects in the selected database. Verify the target and backup before running
it, and stop the application first. See [the microSD restore runbook](./restore.md)
for the production recovery procedure.

Dry run:

```bash
DB_URL="postgresql://postgres@127.0.0.1:5432/fantasy_pi" \
./scripts/restore_db.sh --dry-run /var/backups/fantasy-football-pi/postgres_20260829T000000Z.dump.gz
```

### Restore with the newest backup in `BACKUP_DIR`

```bash
DB_URL="sqlite:////var/lib/fantasy-football-pi/app.db" \
BACKUP_DIR="/var/backups/fantasy-football-pi" \
./scripts/restore_db.sh
```

## Pi automation

Production Pi backup automation uses the supplied systemd timer and writes to
the mounted microSD card. Install the script and unit files from the repository
root:

```bash
sudo mkdir -p /opt/fantasy-football-pi/ops/backup
sudo install -m 0755 ops/backup/microsd_db_backup.sh /opt/fantasy-football-pi/ops/backup/microsd_db_backup.sh
sudo cp deploy/systemd/microsd-db-backup.service.example /etc/systemd/system/microsd-db-backup.service
sudo cp deploy/systemd/microsd-db-backup.timer.example /etc/systemd/system/microsd-db-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now microsd-db-backup.timer
sudo systemctl start microsd-db-backup.service
sudo systemctl status microsd-db-backup.service --no-pager
```

Operational guardrail:

- ensure `/mnt/microsd` is mounted and writable
- ensure the database service is healthy before backup begins
- the unit reads `/etc/fantasy-football-pi/backend.env` for `DATABASE_URL`
- the microSD script retains backups for 14 days by default
- copy the newest snapshot to an off-device target nightly

## Off-device backup

Recommended destinations:

- OneDrive via rclone
- Backblaze B2
- S3-compatible object storage

Example rclone sync from the production microSD backup directory:

```bash
rclone copy /mnt/microsd/backups/fantasy-football-pi remote:fantasy-football-pi-backups
```

This keeps a second copy outside the Pi in case the SD card fails or the device is replaced.

## Monitoring and alerting

If a backup has not succeeded in the last 25 hours, the system should produce
an alert or incident note. The repo includes `scripts/check_backup_status.sh`,
which inspects the latest backup timestamp in the configured `BACKUP_DIR` and
exits non-zero when the newest snapshot is older than the configured
`STALE_HOURS` threshold. This check is separate from the microSD systemd timer;
configure its `BACKUP_DIR` to the location being monitored.

Example cron entry:

```cron
0 * * * * BACKUP_DIR=/mnt/microsd/backups/fantasy-football-pi /home/pi/fantasy-football-pi/scripts/check_backup_status.sh >> /var/log/fantasy-football-pi-check-backup.log 2>&1
```

This keeps backup freshness visible and surfaces a failure before a missing backup becomes a production incident.

## Restore checklist

- stop the application or backend service before restore
- ensure the target database is reachable and writable
- confirm the backup file is the correct environment snapshot
- run the restore command
- validate key table counts while the backend remains stopped
- start the backend, then validate `/health`

## Safety notes

- never expose production `DATABASE_URL` values in git or logs
- keep copies of credentials in secret storage, not committed files
- prefer Postgres for production workloads even when local development remains SQLite
- test restore flow from a real backup artifact before depending on it in production
- treat `scripts/restore_db.sh` as destructive and verify the selected database
  and backup before execution
