# Feature Dictionary — Fantasy Football PI

**Version:** 1.0
**Effective date:** 2026-05-04
**Issue:** #113
**Milestone:** M8 — ML Draft Analyzer and In-Season Intelligence
**Registry source:** [`etl/feature_registry.yml`](../etl/feature_registry.yml)
**Detailed specification:** [`docs/ml-feature-specification.md`](ml-feature-specification.md)

---

## 1. Purpose

This document is the quick-reference dictionary for all ML features in the platform.
It is a human-readable catalog intended for contributors who need to understand:

- What a feature means in plain English
- Whether it is safe to serve at request time (`online`) or ETL/training only (`offline`)
- Which tier controls null-rate alerting
- The deprecation policy so callers know how much notice to expect before removal

For full formulas and computation details, see
[`docs/ml-feature-specification.md`](ml-feature-specification.md).
For the machine-readable authoritative source, see
[`etl/feature_registry.yml`](../etl/feature_registry.yml).

---

## 2. Tier Definitions

| Tier | Null threshold | Impact if missing |
|---|---|---|
| `critical` | ≤ 10 % | Model or endpoint will degrade; CI gate fails |
| `standard` | ≤ 20–30 % | Reduced accuracy; alerts raised in data quality run |
| `optional` | ≤ 40 % | Best-effort; graceful degradation expected |

---

## 3. Online vs Offline

| Tag | Meaning |
|---|---|
| `online: true` | Safe to compute and serve at request time — no future data required |
| `online: false` | **ETL / training only** — requires completed draft or season data; must never appear in live endpoints |

---

## 4. Feature Lifecycle Rules

### 4.1 Adding a feature

1. Add an entry to `etl/feature_registry.yml` with all required fields.
2. Implement computation in `etl/transform/ml_features.py` (or relevant ETL module).
3. Add schema parity test in `backend/tests/` if the feature has a `critical` or `standard` tier.
4. Update this dictionary and `docs/ml-feature-specification.md` in the same PR.

### 4.2 Modifying a feature

- **Non-breaking** (null threshold, documentation, owner field): update registry; no version bump.
- **Breaking** (formula change, output type change, input column rename): bump `version` in the registry entry; update all downstream callers and tests in the same PR.

### 4.3 Deprecating a feature

1. Set a `deprecated_since` field in the registry entry.
2. Add a deprecation warning to the computation module.
3. Notify all callers in the PR description.
4. Remove the feature only after the notice period defined in `deprecation_policy` has passed.
5. Update this dictionary entry with "**DEPRECATED — removed in vX**".

---

## 5. Player-Season Features

These features have one row per `(player_id, season_year)`.

| Feature | Type | Tier | Online | Plain English |
|---|---|---|---|---|
| `points_total` | float | critical | yes | Total fantasy points scored across all weeks in the season |
| `points_avg` | float | critical | yes | Average weekly fantasy points for the season |
| `points_stdev` | float | critical | yes | Week-to-week consistency; higher = more volatile |
| `reliability_score` | float | critical | yes | `points_avg / (points_avg + points_stdev)`. Range 0–1; 1 = perfectly consistent |
| `trend_slope` | float | standard | yes | Linear regression slope of weekly points vs week number; positive = improving in-season |
| `trend_yoy` | float | standard | yes | Season-over-season average points change vs prior year; null for rookies |
| `draft_avg_cost` | float | standard | **no** | Mean auction bid for this player across all historical seasons |
| `draft_max_cost` | float | standard | **no** | Highest auction bid ever paid for this player |
| `draft_median_cost` | float | standard | **no** | Median auction bid for this player across historical seasons |
| `bargain_score` | float | standard | **no** | How cheaply this player was acquired vs position average; positive = bargain |
| `bidding_war_likelihood` | float | optional | **no** | Coefficient of variation of historical bids; higher = more price volatility |
| `positional_scarcity_index` | float | standard | **no** | Fraction of remaining positional picks at the time of draft; 1 = last at position |
| `is_keeper` | bool | critical | yes | `True` if this pick was made as a keeper (bid ≤ $1) |

### Detail notes

**`reliability_score`**
- `> 0.80` — Lock; predictable week-to-week output
- `0.70–0.80` — Solid; manageable variance
- `< 0.70` — High floor/ceiling risk

**`trend_slope`**
- `|slope| > 2.0` — Significant trend
- Requires ≥ 3 weeks to be meaningful

**`bargain_score`**
- Positive = paid less than positional average (good value)
- Negative = overpaid vs positional average

**`bidding_war_likelihood`**
- Requires ≥ 2 historical seasons; null for players with only one draft appearance

---

## 6. Owner-Season Features

These features have one row per `(owner_id, season_year)`.

| Feature | Type | Tier | Online | Plain English |
|---|---|---|---|---|
| `total_spend` | float | critical | yes | Total auction dollars spent by this owner in the season |
| `starting_budget` | float | critical | yes | Budget assigned to this owner at the start of the draft |
| `budget_drift` | float | standard | yes | `(spend - budget) / budget`; positive = overspent; negative = underspent |
| `spend_by_position` | dict | critical | yes | Total spend broken down by position abbreviation (e.g., `{"RB": 72, "WR": 58}`) |
| `position_spend_pct` | dict | critical | yes | `spend_by_position[pos] / total_spend` for each position; sums to 1.0 |
| `max_bid_by_position` | dict | standard | yes | Largest single bid made at each position |
| `avg_bid_by_position` | dict | standard | yes | Average bid made at each position |
| `aggressiveness_index` | float | critical | yes | Fraction of spend concentrated in top-quartile bids; high = stars-and-scrubs strategy |
| `positional_bias_index` | float | critical | yes | How far this owner's positional allocation deviates from league average; 0 = league-average |
| `owner_vs_league_avg_spend` | dict | standard | yes | Per-position delta vs league mean positional allocation |
| `keeper_count` | int | standard | yes | Number of players kept into this season |
| `keeper_spend` | float | standard | yes | Total bid value locked in keeper picks this season |

### Detail notes

**`aggressiveness_index`**
- High value (> 0.6) = owner concentrates spend on a few premium players
- Low value (< 0.3) = owner spreads budget evenly across the roster

**`positional_bias_index`**
- 0.0 = allocates budget exactly like the league average
- > 0.15 = meaningful positional bias (heavy RB, heavy WR, etc.)

---

## 7. Draft-Season Features

These features have one row per `season_year` (league-wide aggregates).

| Feature | Type | Tier | Online | Plain English |
|---|---|---|---|---|
| `league_avg_position_spend_pct` | dict | critical | yes | League-wide fraction of total spend at each position |
| `avg_cost_by_position` | dict | critical | yes | Average winning bid by position across the whole league |
| `inflation_index` | dict | standard | **no** | YoY price change per position vs prior season; positive = prices rose |
| `budget_distribution_gini` | float | standard | **no** | Gini coefficient of total spend across owners; 0 = equal; 1 = monopoly |
| `positional_demand` | dict | standard | yes | Fraction of total picks at each position |
| `replacement_level_value` | dict | standard | **no** | Cost of the last non-keeper pick at each position (floor price) |
| `scarcity_curve_slope` | dict | optional | **no** | How fast prices drop as each positional slot fills; negative = early picks cost more |
| `total_league_spend` | float | critical | yes | Total auction dollars spent by all owners (excluding keepers) |
| `pick_count_by_position` | dict | standard | yes | Count of picks at each position across all owners |

### Detail notes

**`inflation_index`**
- Null for first season in dataset (no prior year)
- Negative value means prices fell vs prior year (deflation)

**`replacement_level_value`**
- Useful for bid capping: any bid below replacement level is likely a bargain

**`budget_distribution_gini`**
- Values above 0.3 suggest meaningful spending inequality across teams

---

## 8. Naming Conventions

| Convention | Rule |
|---|---|
| All feature names | `snake_case` only |
| Player-season | No prefix required (implied by `level: player_season`) |
| Owner-season | No prefix required (implied by `level: owner_season`) |
| Draft-season | No prefix required (implied by `level: draft_season`) |
| Derived features | Name describes the derived quantity, not the computation (e.g., `reliability_score` not `avg_over_avg_plus_stdev`) |
| Boolean features | Prefixed with `is_` or `has_` (e.g., `is_keeper`) |
| Count features | Suffixed with `_count` (e.g., `keeper_count`) |
| Dict features | Suffixed with `_by_{grouping}` or `_pct` (e.g., `spend_by_position`, `position_spend_pct`) |

---

## 9. Related Documents

- [ML Feature Specification](ml-feature-specification.md) — full formulas, computation rules, temporal leakage policy
- [`etl/feature_registry.yml`](../etl/feature_registry.yml) — machine-readable authoritative source
- [Model Versioning and Promotion Rules](model-versioning.md) — feature schema compatibility gates
- [Data Dictionary](data-dictionary.md) — underlying table and column definitions
