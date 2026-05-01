---
name: ml-ops
description: 'Analytics feature development, ML modeling patterns, player/manager metrics, historical data pipelines, consistency scoring, luck index, waiver wire opportunity analysis, and ETL conventions for Fantasy Football PI. Use when: building analytics endpoints, adding new metrics, ETL data pipelines, ML feature engineering, or working with player_weekly_stats.'
argument-hint: 'Optional: focus area (analytics-endpoint | etl | feature-engineering | scoring | modeling)'
---

# ML Ops / Analytics Engineering

## Why This Exists
Fantasy Football PI is evolving toward ML-informed recommendations (lineup advice, breakout detection, trade valuation). All analytics features share common patterns — consistent endpoints, standardized response shapes, shared helpers — so new metrics can be added quickly and reliably.

## Implemented Analytics Features

| Feature | Endpoint | Key Metric |
|---------|----------|------------|
| Manager Efficiency | `/analytics/league/{id}/manager-efficiency` | optimal vs actual lineup score |
| Luck Index | `/analytics/league/{id}/luck-index` | actual wins vs hypothetical wins |
| Player Consistency | `/analytics/league/{id}/player-consistency` | reliability_score = avg/(avg+stdev) |
| Waiver Wire Opportunities | `/analytics/league/{id}/waiver-opportunities` | opportunity_score composite |
| Season Outlook | `/analytics/league/{id}/season-outlook` | post-draft strength projection |
| Draft Value Board | `/analytics/league/{id}/draft-value` | ADP vs actual performance delta |

## Analytics Endpoint Template
```python
@router.get('/league/{league_id}/my-metric')
def get_my_metric(
    league_id: int,
    season: int = Query(None, description="Season year, defaults to current"),
    limit: int = Query(20, ge=5, le=100),
    db: Session = Depends(get_db),
):
    resolved_season = _resolved_season(season)

    # 1. Fetch data (exclude hist_% users)
    # 2. Calculate metric
    # 3. Sort / rank
    # 4. Return standardized response

    return {
        "rows": rows,
        "meta": _analytics_meta(
            db,
            metric="my_metric",
            league_id=league_id,
            season=resolved_season,
        ),
    }
```

## Standard Analytics Helpers
```python
# Season default (use for ALL analytics endpoints)
_resolved_season(season)  → int

# Standardized meta block (use in ALL analytics responses)
_analytics_meta(db, metric, league_id, season)  → dict

# Extract numeric from ESPN stats JSON (handles multiple key name variants)
_extract_numeric(stats_dict, ["key1", "key2", ...])  → float | None

# Linear regression slope (for trend detection)
_calc_slope(values: list[float])  → float
```

## Data Sources

### Player Weekly Stats
Primary source for all player-level analytics:
```python
db.query(models.PlayerWeeklyStat).filter(
    models.PlayerWeeklyStat.season == resolved_season,
    models.PlayerWeeklyStat.player_id.in_(player_ids),
).order_by(models.PlayerWeeklyStat.week).all()
```
- `fantasy_points`: float, computed from ESPN stats
- `stats`: JSON dict with raw ESPN stat keys (inconsistent naming — use `_extract_numeric()`)
- `source`: `"espn"` or `"mfl"`

### ESPN Stat Key Aliases
The `stats` JSON field uses ESPN's raw naming which varies. Common fields:
```python
# Targets (WR/TE)
_extract_numeric(stats, ["TGTS", "targets", "receivingTargets", "Tgt"])

# Carries (RB)
_extract_numeric(stats, ["CAR", "carries", "rushingAttempts", "Att"])

# Red zone targets
_extract_numeric(stats, ["RZTGTS", "redZoneTargets"])

# Fantasy points
_extract_numeric(stats, ["fantasyPoints", "fantasyPointsPPR"])
```

## ML Feature Engineering Principles

### Reliability Score
`reliability_score = avg / (avg + stdev)` — normalized to 0–1. Values:
- > 0.80: Highly reliable starter (lock in lineup)
- 0.70–0.80: Solid, manageable variance
- < 0.70: High floor/ceiling gamble

### Opportunity Score (Waiver Wire)
`opportunity_score = avg_fp + (targets/game × 0.5) + (carries/game × 0.3) + (rz_targets/game × 0.8)`

Weights rationale: RZ targets are highest-value opportunity signal; targets matter more than carries for scoring efficiency.

### Luck Score (Schedule Analysis)
`luck = actual_wins - hypothetical_wins`

Hypothetical wins = how many wins the manager would have if their weekly score was played against every other manager's opponent schedule.
- Positive: Benefited from favorable scheduling
- Negative: Was statistically unlucky

### Trend Slope
Linear regression slope over last N weeks of fantasy points. Interpretation:
- `slope > 2.0`: Breaking out — buy in waivers/trade
- `slope < -2.0`: Declining — possible sell signal
- `|slope| < 2.0`: Stable production

## ETL Pipeline
Historical data comes from two sources:
- **MFL (My Fantasy League)**: Historical season data via `backend/services/mfl_ingestion_service.py`
- **ESPN API**: Current-season weekly stats via `backend/scripts/archive_weekly_stats.py`

ETL runs: `python backend/scripts/archive_weekly_stats.py --season 2025 --week 10`

## Always Do
- Use `_resolved_season()` for every analytics endpoint season parameter
- Use `_analytics_meta()` in every analytics response
- Filter out `hist_%` users before any owner-level computation
- Use `statistics` module for descriptive stats (mean, median, stdev) — no manual calculations
- Return both `most_reliable` AND `most_volatile` for consistency-type metrics (useful for ML features)
- Store `weekly_points` lists in responses — downstream ML models need the raw time series

## Never Do
- Never hard-code a season year
- Never return analytics data without the `meta` block
- Never compute statistics in the router — put in service function or inline only for simple aggregations
- Never delete historical `player_weekly_stats` records — they are the ML training data
- Never assume ESPN stat key names are consistent — always use `_extract_numeric()` with aliases

## Future ML Opportunities
These patterns are specifically designed to enable:
- **Lineup optimizer**: Use reliability_score + projected points for optimal lineup selection
- **Trade valuation**: Combine avg, trend slope, and ceiling for buy/sell ratings
- **Breakout detection**: Trend slope + opportunity score + snap% for waiver pickups
- **Monte Carlo simulation**: Weekly score distributions → season outcome probability

## Related Skills
- [API Patterns](../api-patterns/SKILL.md) — analytics endpoint conventions
- [Database](../database/SKILL.md) — PlayerWeeklyStat queries
- [Architecture](../architecture/SKILL.md) — where analytics logic lives
- [Maintenance](../maintenance/SKILL.md) — ETL schedule, data freshness
