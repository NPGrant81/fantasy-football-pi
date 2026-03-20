### Gap 04 — Database Strategy & Backup Plan

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `database`, `infrastructure`, `backup`, `raspberry-pi`

---

**Summary**

Finalize the database engine choice (SQLite vs PostgreSQL), define the Docker volume strategy for durable data storage, and implement an automated backup and restore workflow including off-device backup.

Currently the project uses SQLite in development and CI, but there is no documented decision or plan for production, no volume strategy, and no backup automation.

---

**Tasks**

- [ ] Document the SQLite vs PostgreSQL decision in an ADR (`docs/adr/adr-003-database-engine.md`) covering trade-offs for Pi hardware and team operational complexity
- [ ] Define and document the Docker named volume strategy for the database (volume name, mount path, backup path)
- [ ] Implement `scripts/backup_db.sh` — snapshot the database (SQLite `.backup` or `pg_dump`), compress, and write to a local backup directory
- [ ] Implement `scripts/restore_db.sh` — restore from a named backup file with a dry-run option
- [ ] Add a systemd timer (or cron) on the Pi to run `backup_db.sh` nightly and retain the last 7 local backups
- [ ] Implement off-device backup upload (rclone to OneDrive, S3, or Backblaze B2) with documented configuration
- [ ] Add backup status monitoring: alert if no successful backup in 25 hours
- [ ] Document the full backup/restore workflow in `docs/DATABASE.md`

---

**Acceptance Criteria**

- ADR documents the database engine choice with rationale
- Docker volume is named and documented; data survives container restarts and upgrades
- `backup_db.sh` produces a restorable, timestamped backup file
- `restore_db.sh` restores a backup to a running instance without data loss
- Nightly backup runs automatically and retains the last 7 snapshots
- At least one off-device backup destination is configured and tested
- Full restore tested from off-device backup copy
- Workflow documented in `docs/DATABASE.md`
