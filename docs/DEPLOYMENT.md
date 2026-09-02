# Deployment automation

This repository includes a lightweight deploy workflow for the Raspberry Pi runtime and local environment.

## Topology Contract

- Development uses Vite on `127.0.0.1:5173` with Docker Compose PostgreSQL on
	`5432`; Compose also provides Redis on `6379` for optional distributed rate
	limiting.
- Production runs native PostgreSQL on the Raspberry Pi. systemd launches
	FastAPI/Uvicorn on `127.0.0.1:8000`, with
	`python -m backend.apply_migrations` as `ExecStartPre`.
- Cloudflare Tunnel forwards to Nginx on the Pi. Nginx serves
	`/var/www/fantasy-football-pi/frontend/dist` and reverse proxies backend route
	families to `127.0.0.1:8000`.
- Redis is not a production requirement. The rate limiter uses in-memory state
	by default and uses Redis only when `RATE_LIMITER_BACKEND=redis` is explicitly
	configured.

## Command summary

From the repository root, the canonical deployment commands are:

```bash
make deploy
make rollback
make restart
make logs
make status
make backup
make restore RESTORE_FILE=/path/to/postgres_20260829T000000Z.dump.gz
```

## What the script does

The helper at `deploy/deploy.sh` wraps the common operational steps needed for a safe deployment:

- record the last good git ref for rollback
- pull the latest repo changes
- apply schema migrations when available
- restart the FastAPI backend service
- verify the backend reaches `/health` before declaring success
- provide operational outputs for logs, status, backup, and restore

## Deployment workflow

```bash
make deploy
```

This should be used for routine production updates or server restarts. The script validates the health endpoint before finishing, which helps prevent a broken deploy from being treated as successful.

## Rollback workflow

```bash
make rollback
```

The previous git ref is recorded before each deploy and reused for a quick rollback path.

## Service lifecycle

```bash
make restart
make logs
make status
```

These commands are intended to simplify the common systemd and log-management flow on the Pi.

## Backup workflow

```bash
make backup
```

This delegates to the backup utility at `ops/backup/microsd_db_backup.sh`, which supports Postgres and SQLite backups with retention cleanup.

## Restore workflow

```bash
make restore RESTORE_FILE=/mnt/microsd/backups/fantasy-football-pi/postgres_2026-01-01_120000.dump.gz
```

Restore actions should be run only after confirming the target database and service state are correct.

## Notes

- These commands are intentionally small and explicit, not a full zero-downtime orchestration system.
- For production-style blue/green or canary deployment, the repo should evolve
	toward a systemd dual-service pattern or a separately approved packaging
	strategy.
- The explicit health check remains the guardrail before a deploy is considered successful.
