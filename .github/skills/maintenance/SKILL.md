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
pip freeze > requirements-lock.txt
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
pg_dump -U postgres fantasy_football > backups/fantasy_$(date +%Y%m%d_%H%M).sql
```

### Automated backup (recommended cron on Pi)
```bash
# Add to crontab: crontab -e
0 3 * * 0 pg_dump -U postgres fantasy_football > /home/pi/backups/fantasy_$(date +\%Y\%m\%d).sql
```

### Restore from backup
```bash
psql -U postgres -d fantasy_football < backups/fantasy_20250501.sql
```

## ETL Schedule

### ESPN weekly stats ingestion
```bash
# Run after each NFL week finalizes (Tuesday morning)
python backend/scripts/archive_weekly_stats.py --season 2025 --week <N>
```

Verify ingestion:
```bash
# Check row count for the week
psql -c "SELECT count(*) FROM player_weekly_stats WHERE season=2025 AND week=<N>;"
```

### MFL historical data
```bash
# One-time per season import for historical leagues
python backend/services/mfl_ingestion_service.py --season <YYYY>
```

## Health Checks

### Backend health endpoint
```bash
curl -s http://localhost:8010/health | jq .
# Expected: {"status": "ok", "db": "connected", "version": "..."}
```

### Service status check
```bash
sudo systemctl status fantasy-backend cloudflared nginx
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
# Check current migration state
cd backend && alembic current

# Check for pending migrations
alembic history | head -5

# Detect if autogenerate finds unapplied changes
alembic revision --autogenerate -m "check" --sql | head -20
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
- Monitor `journalctl -u fantasy-backend` for error spikes after each NFL week
- Keep `requirements-lock.txt` in sync with any `requirements.txt` changes
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
| `alembic heads` shows 2 heads | `alembic merge heads -m "merge_<description>"` |

## Related Skills
- [Database](../database/SKILL.md) — migration procedures
- [Deployment](../deployment/SKILL.md) — service restart procedures
- [Security](../security/SKILL.md) — dependency vulnerability scanning
- [ML Ops](../ml-ops/SKILL.md) — ETL pipeline details
