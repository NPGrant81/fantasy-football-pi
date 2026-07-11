# Season Reset Workflow — Fantasy Football PI

**Version:** 1.0
**Effective date:** 2026-05-04
**Issue:** #113
**Milestone:** M8 — ML Draft Analyzer and In-Season Intelligence
**Owner:** platform-ops

---

## 1. Purpose

This document defines the end-of-season and start-of-season reset workflow.
Following this runbook each season ensures:

- Historical data is archived cleanly
- Keeper selections are reset and re-opened on schedule
- Draft configuration is ready for the new season
- ML feature pipelines are rebased on fresh data
- No stale state from the prior season leaks into the new season

---

## 2. Season Calendar Reference

| Event | Typical timing | System action |
|---|---|---|
| Season end (playoffs complete) | February | Archive weekly stats; finalize standings |
| Keeper window opens | March | Reset keeper locks; open keeper selection |
| Keeper window closes | April | Lock keepers; compute adjusted budgets |
| Draft prep | April–May | Build draft model artifacts; ingest player pool |
| Auction draft | May | Draft Day Mode enabled |
| In-season (Weeks 1–13) | September–December | Live scoring; weekly stats ingestion |
| Playoffs (Weeks 14–16) | December–January | Playoff bracket active |

---

## 3. Post-Season Archive (Phase 1 — End of Season)

Run after playoffs are finalized and scores are locked.

### 3.1 Archive MFL exports

```bash
# Archive CSV exports for the completed season
python backend/scripts/archive_mfl_csv_exports.py --season {YEAR}

# Archive HTML exports
python backend/scripts/archive_mfl_html_exports.py --season {YEAR}

# Archive JSON exports
python backend/scripts/archive_mfl_json_exports.py --season {YEAR}
```

### 3.2 Archive weekly stats

```bash
python backend/scripts/archive_weekly_stats.py --season {YEAR}
```

### 3.3 Validate archive completeness

- Confirm all 16 regular-season weeks are present in `player_weekly_stats` for season `{YEAR}`.
- Confirm final standings match league records.
- Run data quality guardrails:
  ```bash
  python -m pytest backend/tests/test_data_quality_guardrails.py -v
  python -m pytest backend/tests/test_data_quality_seasonal_guardrails.py -v
  python -m pytest backend/tests/test_data_quality_volume_guardrails.py -v
  ```

### 3.4 Finalize the season record

- Mark season `{YEAR}` as completed in the `leagues` table (if applicable).
- Confirm `scoring_week` is at the final week — do not leave it mid-season.

---

## 4. Keeper Window (Phase 2 — Pre-Draft)

### 4.1 Reset keeper selections

Run **before** notifying owners that the new keeper window is open:

```python
# Via Python or FastAPI admin endpoint
from backend.services.keeper_service import reset_keepers
reset_keepers(db=db, league_id=1, season={NEW_YEAR})
```

Or via the admin API:
```
POST /keepers/admin/reset
{
  "season": {NEW_YEAR}
}
```

### 4.2 Open keeper window

```python
from backend.services.keeper_service import send_window_open_notifications
send_window_open_notifications(db=db, league_id=1)
```

Owners now receive an email notification to make keeper selections.

### 4.3 Close keeper window

Once the deadline passes, lock all keeper selections:

```python
# Keepers are locked per-owner as they submit; commissioner locks stragglers
# via the keeper management API or admin UI
```

Verify adjusted budgets are correct:
```
GET /leagues/1/budgets
```
And spot-check owner keeper economics via:
```
GET /keepers/mine?season={NEW_YEAR}
```

---

## 5. Draft Preparation (Phase 3 — Draft Setup)

### 5.1 Ingest new player pool

```bash
# Import current NFL player list
python backend/scripts/import_espn_players.py --season {NEW_YEAR}
# or
python backend/scripts/import_nfl_data.py --season {NEW_YEAR}

# Import NFL schedule
python backend/scripts/import_nfl_schedule.py --season {NEW_YEAR}
```

### 5.2 Rebuild ML feature artifacts

```bash
# Recompute player and season features using all completed history
python etl/build_historical_rankings.py --target-season {NEW_YEAR}
```

Confirm the feature registry passes schema validation:
```bash
python -m pytest backend/tests/test_data_quality_guardrails.py -k "feature" -v
```

### 5.3 Evaluate challenger model (if applicable)

If a new model version is being promoted this season, complete the full
promotion workflow per `docs/model-versioning.md` before the draft date.

### 5.4 Smoke test Draft Day Mode

```bash
python -m pytest backend/tests/test_advisor_draft_day.py -v
python -m pytest backend/tests/test_draft_simulation_endpoint.py -v
```

### 5.5 Initialize league configuration for new season

```bash
python backend/scripts/init_league.py --season {NEW_YEAR}
```

Confirm league settings (roster slots, scoring rules, salary cap) in the admin UI
or via `GET /league/settings`.

---

## 6. In-Season Setup (Phase 4 — Season Start)

### 6.1 Enable live scoring

Confirm the live scoring watchdog service is running:
```bash
systemctl status ffpi-live-scoring
# or check the watchdog endpoint
GET /live-scoring/status
```

### 6.2 Verify weekly ingestion schedule

Confirm that the ETL daily sync job is scheduled and healthy:
```bash
python -m pytest backend/tests/test_live_scoring_watchdog_service.py -v
```

### 6.3 Verify in-season analytics

Smoke test in-season endpoints:
```bash
python -m pytest backend/tests/test_analytics.py -k "in_season" -v
python -m pytest backend/tests/test_advisor_router.py -k "in_season" -v
```

---

## 7. Season Reset Checklist

Use this checklist at each season boundary. Check off each item before
proceeding to the next phase.

### End of season

- [ ] All playoff scores locked and finalized
- [ ] MFL CSV/HTML/JSON exports archived for season `{YEAR}`
- [ ] Weekly stats archived for season `{YEAR}`
- [ ] Data quality guardrail tests pass
- [ ] Final standings confirmed accurate

### Keeper window

- [ ] `reset_keepers()` called for the new season
- [ ] Keeper window-open notification sent to all owners
- [ ] All owners have submitted keeper selections (or commissioner has closed stragglers)
- [ ] Adjusted budgets verified for all owners

### Draft prep

- [ ] New player pool ingested
- [ ] NFL schedule imported
- [ ] ML feature artifacts rebuilt with new history
- [ ] Model version confirmed (no challenger pending) or new model promoted per `docs/model-versioning.md`
- [ ] Draft Day Mode smoke tests pass
- [ ] League configuration initialized for new season

### Season start

- [ ] Live scoring watchdog running
- [ ] Weekly ETL ingestion job scheduled
- [ ] In-season analytics smoke tests pass
- [ ] All owners can access their locker room

---

## 8. Rollback Notes

If any phase fails partway through:

- **Archive scripts**: re-running is safe; they are idempotent for completed seasons.
- **Keeper reset**: `reset_keepers()` is idempotent; safe to re-run.
- **ML rebuild**: re-run `build_historical_rankings.py`; does not affect production until model is promoted.
- **Live scoring**: restart the watchdog service; weekly stats are ingested incrementally.

---

## 9. Related Documents

- [Model Versioning and Promotion Rules](model-versioning.md)
- [Deployment Workflows](DEPLOYMENT_WORKFLOWS.md)
- [Data Quality Runbook](DATA_QUALITY_RUNBOOK.md)
- [Draft Day Advisor Mode](DRAFT_DAY_ADVISOR_MODE.md)
- [Raspberry Pi Deployment](RASPBERRY_PI_DEPLOYMENT.md)
