---
name: ml-ops
description: 'Analytics feature development and MLOps lifecycle for Fantasy Football PI: feature engineering, model training and evaluation, champion or challenger promotion, drift detection, simulation impact measurement, serving integration, and ETL conventions. Use when: building analytics endpoints, training models, defining evaluation gates, adding drift monitoring, integrating serving contracts, or hardening model operations.'
argument-hint: 'Optional: focus area (analytics-endpoint | etl | feature-engineering | training-eval | drift | champion-challenger | scoring | serving | observability | modeling)'
---

# ML Ops / Analytics Engineering

## Why This Exists
Fantasy Football PI is evolving toward ML-informed recommendations (lineup advice, breakout detection, trade valuation). All analytics features share common patterns — consistent endpoints, standardized response shapes, shared helpers — so new metrics can be added quickly and reliably.

This skill also defines the required MLOps process for Issue #108 and later model iterations.

## Standard MLOps Lifecycle (Required)

1. Target and label definition
    - Define target variables and business interpretation.
    - Use strict time-based train, validation, and test splits.
2. Dataset and feature assembly
    - Consume feature contracts from Issue #106 outputs.
    - Persist dataset version and feature schema hash.
3. Candidate training
    - Train baseline and advanced models using identical splits.
    - Persist params, seed, and environment metadata.
4. Offline evaluation
    - Regression: MAE, RMSE, median AE.
    - Ranking quality: NDCG at K, MAP at K.
    - Calibration: bucket error or calibration curve stats where applicable.
5. Simulation impact evaluation
    - Route candidate outputs through the Issue #107 bridge path.
    - Compare authenticated-owner slice outcomes and required slices vs champion.
6. Champion or challenger decision
    - Promote only when all gates pass.
    - Store auditable decision record and model card.
7. Post-promotion monitoring
    - Monitor drift and performance degradation.
    - Trigger retraining when thresholds are breached.

## Required MLOps Artifacts

Every training run must produce:

- model artifact URI
- dataset version and feature schema hash
- training config and split definition
- evaluation report with slice metrics
- simulation impact report
- model card
- champion or challenger decision record

## Recommended Model Portfolio

Train and compare the following candidates by default:

1. Baseline: historical averages by season and position with inflation adjustments.
2. Interpretable benchmark: Elastic Net.
3. Tabular performance models: Random Forest, LightGBM, CatBoost.
4. Ranking objective model when relevant: pairwise ranking or LambdaMART.
5. Optional uncertainty model: quantile regression for bid ranges.

Select winners using a composite score that includes predictive metrics and simulation outcome impact.

## Promotion Gates (Minimum)

- no more than 10 percent regression on primary error metrics versus champion
- no more than 5 percent regression on ranking metrics
- no significant degradation on required slices, including authenticated-owner context
- reproducible rerun within tolerance
- neutral or positive simulation impact on required owner slices

## Drift Detection and Response

Track three drift categories:

- data drift
  - PSI on key numeric features (warn above 0.2, critical above 0.3)
  - categorical distribution shifts by position and owner slice
- concept and performance drift
  - rolling MAE and RMSE deltas vs champion
  - rolling ranking metric deltas
  - calibration drift over prediction buckets
- decision-impact drift
  - simulation uplift degradation vs champion

Critical drift or sustained degradation requires immediate challenger retraining.

## Tuning and Evaluation Cadence

- every data refresh: data-contract checks and drift checks
- weekly during active draft prep: score-only evaluation against champion
- monthly: full challenger retrain and evaluation cycle
- preseason mandatory refresh: full retrain and model card update
- event-driven retrain: any critical drift or repeated quality gate failure

## Serving Integration Guardrails (Issue #109)

- Serving contract must support authenticated-owner default context (owner-specific personalization).
- Response must include model provenance metadata (requested alias, resolved alias, route strategy).
- Error detail should use typed codes for reliable client handling.
- Serving logs/metrics should track latency, error rate, and fallback rate.
- Canary routing should be alias-controlled and reversible.

Operational hooks currently used:

- `MODEL_SERVING_CURRENT_ALIAS`
- `MODEL_SERVING_CANARY_ALIAS`
- `MODEL_SERVING_CANARY_PERCENT`
- `prometheus_client` dependency for serving observability instrumentation

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

## Issue #108 Implementation Checklist

When implementing Issue #108 work items, ensure the change includes:

1. Defined targets, labels, and split policy in docs.
2. Baseline and at least one advanced model candidate.
3. Evaluation report with regression, ranking, and slice metrics.
4. Simulation impact comparison versus current champion.
5. Drift thresholds and monitoring hooks.
6. Model card and promotion decision record.

## Related Skills
- [API Patterns](../api-patterns/SKILL.md) — analytics endpoint conventions
- [Database](../database/SKILL.md) — PlayerWeeklyStat queries
- [Architecture](../architecture/SKILL.md) — where analytics logic lives
- [Maintenance](../maintenance/SKILL.md) — ETL schedule, data freshness

## Validation Architecture Hooks (Issue #76)

For ETL or analytics data-shaping changes:
1. Run DataFrame schema validation via `etl.validation.dataframe_validation`.
2. Run expectations validation via `etl.validation.great_expectations_runner`.
3. Fail load paths on invalid reports; do not continue with partial writes.
4. Add/adjust tests in `etl/test_validation_framework.py` for both valid and invalid payloads.
