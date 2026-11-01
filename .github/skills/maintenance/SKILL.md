---
name: maintenance
description: 'Dependency updates, database backups, logging conventions, health checks, ETL schedule, seasonal data archival, Pi hardware monitoring, and operational runbooks for Fantasy Football PI. Use when: updating dependencies, scheduling maintenance, checking system health, archiving season data, or planning pre/post-season ops.'
argument-hint: 'Optional: focus area (dependencies | backups | logging | etl | seasonal | health | pi)'
---

# Maintenance

## Why This Exists
Fantasy Football PI is a seasonal app on constrained hardware (Raspberry Pi 4). Data accumulates year over year, dependencies drift, and ESPN/MFL API responses evolve. Structured maintenance windows prevent production surprises during the season.

## Seasonal Calendar

| Window | Tasks |
|--------|-------|
| **Pre-season (July/Aug)** | Dependency audit, DB backup, data import setup, Cloudflare tunnel check |
| **Draft week** | Verify ESPN/MFL API keys, test ETL pipeline, smoke test all endpoints |
| **Week 1** | Monitor logs for API errors, verify player stats ingestion |
| **End of regular season (Wk 14-18)** | Archive weekly stats, snapshot standings |
| **Post-season (Feb/Mar)** | Archive full season, dependency update cycle |
| **Off-season** | Address backlog, test migrations, infra upgrades |

## Dependency Management

### Audit cadence: pre-season + post-season
```bash
# Backend — check for outdated packages
pip list --outdated

# Check for known vulnerabilities
pip-audit   # (install: pip install pip-audit)

# Frontend — check for outdated
cd frontend && npm outdated

# Check for vulnerabilities
npm audit
```

### Updating dependencies
```bash
# Backend — update one package at a time, re-run tests
pip install <package>==<new-version>
pip freeze > backend/requirements-lock.txt
python -m pytest   # verify nothing broke

# Frontend
npm update <package>
npm test -- --run && npm run build   # verify
```

### Validation stack dependency checks (Issue #76)
```bash
# Confirm optional validation engines resolve and import
pip install -r backend/requirements-validation.txt
python -m pytest backend/tests/test_validation_service.py -q
python -m pytest etl/test_validation_framework.py -q
```

If this fails, treat as data-quality gate failure (not optional maintenance noise).

**Never update multiple major dependencies simultaneously.** One at a time.

See `backend/dependency-report.md` and `docs/DEPENDENCY_MAINTENANCE.md` for historical notes.

## Logging Conventions
```python
# ✅ Correct — use the project logger
import logging
logger = logging.getLogger('fantasy')
logger.info("Matchup scored: league=%d week=%d", league_id, week)
logger.warning("ESPN API slow response: %dms", elapsed_ms)
logger.error("Waiver claim failed: player_id=%d error=%s", player_id, str(e))

# ❌ Never
print("debug:", value)
```

Log levels:
- `DEBUG`: Development only (never in production paths)
- `INFO`: Normal operation events (ingestion completed, service started)
- `WARNING`: Degraded but functional (slow API, missing optional data)
- `ERROR`: Failures that affect users (failed claim, scoring error)

**Never log:** secrets, tokens, PII (player names alone are fine; combined with owner data, consider sensitivity)

## Database Backups

### Manual backup (before migrations)
```bash
# Production Pi: run the unit that loads the protected backend environment file.
sudo systemctl start microsd-db-backup.service
sudo systemctl status microsd-db-backup.service --no-pager
```

Verify that a fresh artifact was written before proceeding. The generic
repository backup script can instead write to a chosen `BACKUP_DIR`; see
`docs/DATABASE.md`. Keep the database URL in a protected environment source.

### Automated backup (systemd timer on Pi)
```bash
# Install and enable the supplied microSD backup service and timer.
# See docs/restore.md for the complete setup and verification steps.
sudo systemctl enable --now microsd-db-backup.timer
sudo systemctl start microsd-db-backup.service
sudo systemctl status microsd-db-backup.service --no-pager
```

### Restore from backup
```bash
# Follow the guarded target/backup checks in docs/restore.md.
./scripts/restore_db.sh /path/to/verified-backup.dump.gz
```

## ETL Schedule

### ESPN weekly stats ingestion
```bash
# Run after the selected NFL week finalizes (Tuesday morning)
python backend/scripts/archive_weekly_stats.py <SEASON> <WEEK>
```

Verify ingestion:
```bash
# Check row count for the selected week
psql -c "SELECT count(*) FROM player_weekly_stats WHERE season=<SEASON> AND week=<WEEK>;"
```

### MFL historical data
```bash
# Start with the supported extraction CLI; follow the runbook for import and reconciliation.
python -m backend.manage extract-mfl-history --help
```
See `docs/data-migration/mfl-migration-runbook.md` for the supported
extract/import/reconcile workflow.

## Health Checks

### Backend health endpoint
```bash
curl -fsS http://127.0.0.1:8000/health | jq .
# Healthy response has status="ok", database="ok", and schema="ok".
```

### Service status check
```bash
sudo systemctl status fantasy-football-backend cloudflared nginx --no-pager
```

### Pi hardware monitoring
```bash
# CPU temperature (should be < 70°C under load)
vcgencmd measure_temp

# Disk space (root partition should have > 2GB free)
df -h /

# Memory
free -h
```

## Alembic Migration Health
```bash
# Compare the database revision with the canonical graph (using the intended DB URL)
cd backend && alembic current && alembic heads

# Review migration history
alembic history --verbose

# Apply through the guarded project runner from the repository root
cd .. && python -m backend.apply_migrations
```

## Data Retention Policy
- **Weekly stats**: Keep forever — primary ML training data
- **Matchup results**: Keep forever — historical analytics
- **Transaction history**: Keep forever — audit trail
- **Waiver claims**: Keep forever — dispute resolution
- **Bug reports**: Purge resolved reports > 1 year old (manual)
- **Site visits**: Archive or purge > 2 years old

## Always Do
- Run `pip-audit` before every pre-season to catch CVEs in dependencies
- Back up the database before any production migration
- Check disk space on the Pi monthly (SD cards fill up)
- Monitor `journalctl -u fantasy-football-backend` for error spikes after each NFL week
- Keep `backend/requirements-lock.txt` in sync with backend requirement changes
- Keep `backend/requirements-validation.txt` aligned with validation engines used in code
- Document dependency decisions in `docs/DEPENDENCY_MAINTENANCE.md`

## Never Do
- Never update Python runtime on the Pi during the active season
- Never purge `player_weekly_stats` — it's the analytics/ML source of truth
- Never run `pip install --upgrade` broadly — always targeted updates
- Never ignore `npm audit` findings rated HIGH or CRITICAL

## Common Problems & Remediation

| Problem | Fix |
|---------|-----|
| Pi overheating (> 80°C) | Add heatsink; reduce background processes |
| SD card full | Archive old logs; purge `__pycache__`; consider SSD |
| ESPN API key expired | Refresh `ESPN_S2` and `ESPN_SWID` cookies from browser |
| MFL API rate limit | Add exponential backoff in ingestion script |
| `alembic heads` shows 2 heads | Create a reviewed merge with `alembic -c backend/alembic.ini merge heads -m "merge_<description>"`, then apply through `python -m backend.apply_migrations` |

## Related Skills
- [Database](../database/SKILL.md) — migration procedures
- [Deployment](../deployment/SKILL.md) — service restart procedures
- [Security](../security/SKILL.md) — dependency vulnerability scanning
- [ML Ops](../ml-ops/SKILL.md) — ETL pipeline details
