---
name: database
description: 'Database schema, SQLAlchemy ORM models, Alembic migrations, seeding, and PostgreSQL conventions for Fantasy Football PI. Use when: adding/changing models, writing migrations, querying patterns, schema design questions, database troubleshooting, or asking about historical user exclusion.'
argument-hint: 'Optional: focus area (migration | model | query | seed | troubleshoot)'
---

# Database

## Why This Exists
The Fantasy Football PI database holds all league, player, matchup, and analytics data accumulated over multiple seasons including historical MFL imports. Schema integrity and migration discipline are critical — bad migrations can corrupt multi-year data.

## Tech Stack
- **ORM**: SQLAlchemy (models in `backend/models.py` and `backend/models/`)
- **Migrations**: Alembic (`backend/alembic/`, config at `backend/alembic.ini`)
- **Database**: PostgreSQL 14+
- **Connection**: `backend/database.py` — provides `SessionLocal` and `get_db` dependency
- **Seeding**: `backend/scripts/seed_data.py`, `db/seeds/`

## Critical Rule: Historical User Exclusion
Historical franchise users imported from MFL have usernames matching `hist_YYYY_XXXX` (e.g. `hist_2003_0002`).

**Every query returning a list of league members MUST exclude them:**
```python
db.query(models.User).filter(
    models.User.league_id == league_id,
    models.User.is_superuser.is_(False),
    ~models.User.username.like("hist_%"),   # ← REQUIRED
)
```
Failure to include this filter causes historical ghost users to appear in standings, waivers, and trade interfaces.

## Model Structure
All primary models are in `backend/models.py`. Key tables:

| Table | Model | Purpose |
|-------|-------|---------|
| `users` | `User` | League members + historical imports |
| `leagues` | `League` | League config, commissioner |
| `league_settings` | `LeagueSettings` | Scoring profile, playoff config |
| `players` | `Player` | NFL player registry |
| `player_weekly_stats` | `PlayerWeeklyStat` | ESPN stats JSON + fantasy points per week |
| `matchups` | `Matchup` | Weekly head-to-head results |
| `draft_picks` | `DraftPick` | Draft history + current ownership |
| `transaction_history` | `TransactionHistory` | waiver_add, waiver_drop, drop, trade |
| `waiver_claims` | `WaiverClaim` | FAAB bids and claim outcomes |
| `playoff_snapshots` | `PlayoffSnapshot` | End-of-season bracket snapshots |
| `manager_efficiency` | `ManagerEfficiency` | Analytics: optimal vs actual lineup |

## Always Do
- Write an Alembic migration for every `models.py` change before committing
- Name migrations descriptively: `alembic revision -m "add_player_weekly_stats_source_column"`
- Always add `nullable=True` or a `server_default` for new columns on existing tables
- Use `UniqueConstraint` at the model level for business-key uniqueness
- Close sessions properly — use `Depends(get_db)` in FastAPI, or `with SessionLocal() as db:` in scripts
- Back up the database before running `alembic upgrade head` on production

## Never Do
- Never write raw SQL (`db.execute(text(...))` is banned except in migration scripts)
- Never drop columns in the same migration that removes them from the model — do it in two steps
- Never modify `alembic/env.py` without explicit request
- Never hard-delete historical data — use soft deletes or archive tables
- Never run `alembic downgrade` on production without a full backup
- Never use `db.query(models.User)` without the `hist_%` exclusion when listing members

## Migration Workflow
```bash
# 1. Make changes to backend/models.py

# 2. Generate a migration (review the generated file carefully!)
alembic revision --autogenerate -m "describe_change"

# 3. Review backend/alembic/versions/<hash>_describe_change.py
#    Autogenerate is not perfect — verify upgrade() and downgrade()

# 4. Apply locally
alembic upgrade head

# 5. Test, then commit the migration file with your model changes
git add backend/alembic/versions/ backend/models.py
```

## Common Problems & Remediation

| Problem | Cause | Fix |
|---------|-------|-----|
| `Can't locate revision identifier` | Out-of-sync migration history | `alembic history --verbose` to find divergence |
| `Multiple heads` | Concurrent migrations on different branches | `alembic merge heads -m "merge"` |
| `Column already exists` | Migration applied twice | Check `alembic_version` table; mark revision current if needed |
| `hist_%` users in member lists | Missing exclusion filter | Add `~models.User.username.like("hist_%")` |
| Slow analytics queries | Missing index | Add `index=True` to frequently filtered columns |
| Migration breaks prod | Destructive change | Always add columns as nullable; drop in follow-up migration |

## Query Patterns

### Standard list query
```python
db.query(models.Player).filter(
    models.Player.position.in_(["QB", "RB", "WR"]),
    models.Player.espn_id.isnot(None),
).order_by(models.Player.name).all()
```

### Subquery for exclusion
```python
owned_ids = db.query(models.DraftPick.player_id).filter(
    models.DraftPick.league_id == league_id
)
db.query(models.Player).filter(
    ~models.Player.id.in_(owned_ids)
).all()
```

### Upsert pattern
```python
existing = db.query(Model).filter(Model.unique_key == value).first()
if existing:
    existing.field = new_value
else:
    db.add(Model(field=new_value))
db.commit()
```

## Related Skills
- [Architecture](../architecture/SKILL.md) — ORM layer placement
- [API Patterns](../api-patterns/SKILL.md) — how schemas map to models
- [Project Bootstrap](../project-bootstrap/SKILL.md) — running migrations locally
- [Migration Runbook](./references/migration-runbook.md) — step-by-step production migration guide
