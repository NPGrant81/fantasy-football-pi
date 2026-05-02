# ML Feature Specification — Fantasy Football PI

**Version:** 1.0  
**Effective date:** 2026-05-02  
**Issue:** #106  
**Milestone:** M8 — ML Draft Analyzer and In-Season Intelligence  
**Registry:** [`etl/feature_registry.yml`](../etl/feature_registry.yml)  
**Computation module:** [`etl/transform/ml_features.py`](../etl/transform/ml_features.py)

---

## 1. Purpose

This document is the authoritative specification for all machine learning features
powering the PPL Draft Analyzer and future AI recommendation agents. It defines:

- What every feature is and why it exists
- The exact formula used to compute it
- Which data sources it depends on
- Whether it is safe for online (request-time) serving or offline (ETL/training) only
- Temporal leakage rules and null-rate thresholds

All feature metadata lives in **`etl/feature_registry.yml`** — this doc renders
and explains that registry. If the registry and this document disagree, the
registry is authoritative.

---

## 2. Feature Level Taxonomy

| Level | Description | Primary Key | Computation Module |
|---|---|---|---|
| `player_season` | One row per player per season | `(player_id, season_year)` | `etl/transform/ml_features.py` |
| `owner_season` | One row per owner per season | `(owner_id, season_year)` | `etl/transform/owner_budget_timeline.py` + extensions |
| `draft_season` | One row per season (league-wide) | `season_year` | `etl/transform/ml_features.py` |

---

## 3. Online vs Offline Availability

All features are tagged with `offline: true/false` and `online: true/false` in the registry.

| Tag | Meaning |
|---|---|
| `offline: true` | Available in ETL pipeline; safe for model training |
| `online: true` | Safe to serve at request time; does not require future data |
| `online: false` | **Must not** be served live — requires completed-draft/season data |

> **Rule:** Any feature marked `online: false` must be excluded from all
> FastAPI analytics endpoints. These features are ETL-only and live in the
> `etl/outputs/` directory.

---

## 4. Temporal Leakage Policy

Every feature in the registry carries a `temporal_leakage_guard` field. The
following rules are enforced at computation time:

1. **Weekly scoring features** — only weeks `<= scoring_cutoff_week` are
   included. Never use partial-week data.
2. **Historical cost features** (`draft_avg_cost`, `draft_max_cost`, etc.) —
   when `reference_season` is supplied, only seasons `< reference_season` are
   included. Default (no `reference_season`) is historical analysis mode.
3. **Inflation index** — always computed from *completed* prior season.
   Never compare current-season partial data.
4. **Scarcity curve / replacement level** — completed season only.

---

## 5. Feature Dictionary

### 5.1 Player-Season Features

#### `points_total`
- **Formula:** `SUM(fantasy_points)` across all weeks in season
- **Source:** `player_weekly_stats.fantasy_points`
- **Null threshold:** 5 % (critical)
- **Online:** yes
- **Notes:** Use `_extract_numeric()` to handle ESPN stat key variants.

#### `points_avg`
- **Formula:** `MEAN(fantasy_points)` across all weeks in season
- **Source:** `player_weekly_stats.fantasy_points`
- **Null threshold:** 5 % (critical)
- **Online:** yes

#### `points_stdev`
- **Formula:** `STDEV(fantasy_points)` across all weeks in season
- **Source:** `player_weekly_stats.fantasy_points`
- **Null threshold:** 10 % (critical)
- **Online:** yes
- **Notes:** Requires ≥ 2 weeks; null for single-week players.

#### `reliability_score`
- **Formula:** `points_avg / (points_avg + points_stdev)`
- **Range:** 0–1. Higher = more consistent week-to-week.
- **Interpretation:**
  - `> 0.80` — Lock in the lineup
  - `0.70–0.80` — Solid, manageable variance
  - `< 0.70` — High floor/ceiling risk
- **Source:** derived from `points_avg`, `points_stdev`
- **Online:** yes
- **Implemented in:** `backend/routers/analytics.py :: get_player_consistency`

#### `trend_slope`
- **Formula:** Linear regression slope of `fantasy_points` vs `week`
- **Interpretation:** `slope > 2.0` = breakout; `slope < -2.0` = declining
- **Source:** `player_weekly_stats`
- **Online:** yes
- **Implemented in:** `backend/routers/analytics.py :: _calc_slope`

#### `trend_yoy`
- **Formula:** `points_avg(season) - points_avg(season - 1)`
- **Null:** for rookie season (no prior year)
- **Temporal leakage:** prior season must be fully completed
- **Online:** yes (uses completed prior season)

#### `draft_avg_cost`
- **Formula:** `MEAN(winning_bid)` for this player across all seasons in history
- **Temporal leakage:** `reference_season` parameter gates which seasons count
- **Online:** **no** — full draft history required
- **Null threshold:** 15 %
- **Null threshold:** 20 %

#### `draft_max_cost`
- **Formula:** `MAX(winning_bid)` for this player across all seasons
- **Online:** **no**

#### `draft_median_cost`
- **Formula:** `MEDIAN(winning_bid)` for this player across all seasons
- **Online:** **no**

#### `bargain_score`
- **Formula:** `(position_avg_cost_this_season - winning_bid) / position_avg_cost_this_season`
- **Interpretation:** Positive = cheaper than position average (bargain); Negative = overpaid
- **Source:** `validated_draft_results`, `feature.avg_cost_by_position`
- **Online:** **no** — position average only known after draft completes

#### `bidding_war_likelihood`
- **Formula:** `STDEV(winning_bid) / MEAN(winning_bid)` (coefficient of variation)
- **Requires:** ≥ 2 historical seasons for this player
- **Higher value:** more price volatility = more likely to trigger bidding wars
- **Online:** **no**
- **Null threshold:** 40 % (optional feature)

#### `positional_scarcity_index`
- **Formula (historical):** `picks_at_position / total_picks_in_season`
- **Interpretation:** Higher fraction = more roster spots allocated to this position
- **Online:** **no** (requires completed draft)

#### `is_keeper`
- **Formula:** `winning_bid <= 1.0`
- **Threshold constant:** `KEEPER_BID_THRESHOLD = 1.0` in `historical_draft_validator.py`
- **Online:** yes
- **Null threshold:** 0 % (always computable)

---

### 5.2 Owner-Season Features

> Behavioral features (`aggressiveness_index`, `positional_bias_index`,
> `spend_by_position`, etc.) are computed by
> `etl/transform/owner_budget_timeline.build_owner_behavior_features()`.
> This section documents those features plus the extensions added by
> `etl/transform/ml_features.compute_owner_season_extensions()`.

#### `total_spend`
- **Formula:** `SUM(winning_bid)` for all picks by owner in season
- **Online:** yes

#### `starting_budget`
- **Formula:** Budget assigned to owner at draft start (from budget timeline)
- **Online:** yes

#### `budget_drift`
- **Formula:** `(total_spend - starting_budget) / starting_budget`
- **Positive:** overspent relative to allotted budget
- **Negative:** underspent
- **Online:** yes

#### `spend_by_position`
- **Formula:** `SUM(winning_bid)` grouped by position abbreviation per owner per season
- **Format:** `{"QB": 45.0, "WR": 120.0, ...}`
- **Online:** yes

#### `position_spend_pct`
- **Formula:** `spend_by_position[pos] / total_spend` — normalized, sums to 1.0
- **Online:** yes

#### `max_bid_by_position`
- **Formula:** `MAX(winning_bid)` per position per owner per season
- **Online:** yes

#### `avg_bid_by_position`
- **Formula:** `MEAN(winning_bid)` per position per owner per season
- **Online:** yes

#### `aggressiveness_index`
- **Formula:** `SUM(top-quartile bids) / total_spend`
  - Top quartile = top 25 % of owner's bids by value
- **Range:** 0–1. Higher = more spend concentrated on a few premium players.
- **Online:** yes

#### `positional_bias_index`
- **Formula:** Mean Absolute Deviation of `position_spend_pct` from `league_avg_position_spend_pct`
- **Higher:** more positionally biased than the league average
- **Online:** yes

#### `owner_vs_league_avg_spend`
- **Formula:** `position_spend_pct[pos] - league_avg_position_spend_pct[pos]` for each position
- **Format:** `{"QB": 0.03, "WR": -0.05, ...}`
- **Positive:** over-indexed vs league; Negative: under-indexed
- **Online:** yes

#### `keeper_count`
- **Formula:** `COUNT(picks)` where `is_keeper = True` per owner per season
- **Online:** yes

#### `keeper_spend`
- **Formula:** `SUM(winning_bid)` where `is_keeper = True` per owner per season
- **Online:** yes

---

### 5.3 Draft-Season Features

#### `total_league_spend`
- **Formula:** `SUM(winning_bid)` for all picks in season (including keepers)
- **Formula:** `SUM(winning_bid)` for all non-keeper picks in season
- **Online:** yes

#### `avg_cost_by_position`
- **Formula:** `MEAN(winning_bid)` per position for all picks in season
- **Format:** `{"QB": 12.4, "WR": 18.7, ...}`
- **Online:** yes (completed season)

#### `league_avg_position_spend_pct`
- **Formula:** `SUM(bid at position) / SUM(all bids)` per position
- **Online:** yes

#### `pick_count_by_position`
- **Formula:** `COUNT(picks)` per position in season
- **Online:** yes

#### `positional_demand`
- **Formula:** `pick_count_by_position[pos] / total_picks` — normalized fraction
- **Online:** yes

#### `budget_distribution_gini`
- **Formula:** [Gini coefficient](https://en.wikipedia.org/wiki/Gini_coefficient) of `total_spend` across all owners
- **Range:** 0 = equal spend; 1 = one owner spent everything
- **Online:** **no** — requires all owners' completed spend

#### `replacement_level_value`
- **Formula:** `MIN(winning_bid)` for non-keeper picks at each position in season
- **Interpretation:** Marginal cost of the last/cheapest meaningful pick at position
- **Format:** `{"QB": 3.0, "WR": 1.0, ...}`
- **Online:** **no**

#### `inflation_index`
- **Formula:** `avg_cost_by_position(season) / avg_cost_by_position(season - 1) - 1`
- **Positive:** prices rose year-over-year; Negative: prices fell
- **Null:** for first season in data
- **Temporal leakage:** prior season must be fully completed
- **Online:** **no**

#### `scarcity_curve_slope`
- **Formula:** Linear regression slope of `winning_bid` vs pick order within position (sorted by bid descending)
- **Interpretation:** Negative slope = first pick in position costs most (normal); near-zero = flat pricing
- **Online:** **no**

---

## 6. Training/Serving Parity Plan

Parity checks ensure that features computed offline (ETL) match what would be
computed at request time for the same input data.

### 6.1 Shared Sample
For each release, a **golden dataset** is extracted from `validated_draft_results`
for seasons 2021–2024 and stored at `etl/outputs/parity_golden_sample.csv`.

### 6.2 Parity Test Suite
`etl/test_ml_features.py` implements:

| Test | Threshold |
|---|---|
| `test_deterministic_on_repeated_calls` | Exact match on 2 consecutive runs |
| `test_bargain_score_positive_when_below_position_avg` | bargain_score > 0 when bid < position avg |
| `test_inflation_index_null_for_first_season` | inflation_index is None for first season |
| `test_reference_season_excludes_future` | Asserts prior-seasons-only leakage guard |

### 6.3 Parity Metrics (observability)

| Metric | Alert threshold |
|---|---|
| `feature_null_rate` | Exceeds `null_rate_threshold` in registry |
| `parity_mismatch_count` | > 0 for critical features |
| `drift_score` | Any critical feature mean drifts > 20 % from prior season |
| `registry_validation_failures` | > 0 |

---

## 7. Feature Versioning and Governance

### 7.1 Version policy
- Bump `version` in `feature_registry.yml` on any **breaking change** (formula, output type, key rename).
- Non-breaking additions (new optional feature) do not require a version bump.
- Consumers select a version via the `feature_set_version` parameter (future).

### 7.2 Deprecation policy
- **Critical features:** 2-season notice; provide alias column for backward compatibility.
- **Standard/Optional features:** 1-season notice.
- Deprecated features are marked `deprecated: true` in the registry before removal.

### 7.3 Owner SLA
All current features are owned by **ml-ops** (this codebase). When additional
data science contributors are onboarded, ownership can be transferred per-feature
in the registry.

---

## 8. Data Quality Gates

Before publishing any feature set version:

| Gate | Rule |
|---|---|
| Null-rate check | `null_rate ≤ null_rate_threshold` for all critical features |
| Range check | `bargain_score ∈ (-1, 1)`, `aggressiveness_index ∈ (0, 1)`, `reliability_score ∈ (0, 1)` |
| Cardinality check | `position_id` maps to known abbreviation for ≥ 95 % of rows |
| Schema check | All registry-declared columns present in output DataFrame |
| Parity check | 0 mismatches for critical features on golden sample |

---

## 9. Rollout and Rollback

1. New feature set is computed on a canary season (most recent completed season).
2. Parity checks must pass before promoting to `v_next`.
3. Rollback: re-run ETL with prior `etl_version` tag; outputs are versioned in `etl/outputs/`.

---

## 10. Relates To

| Issue | Description |
|---|---|
| #102 | Player metadata canonicalization (Phase 1) |
| #103 | Position registry and canonical snapshot |
| #104 | Owner budget behavior features |
| #105 | Historical draft results validation |
| #107 | Monte Carlo Draft Simulation Framework |
| #451 | ETL write-back for position data |
| #455 | New-season player position gaps (recurring) |
