# Monte Carlo Draft Simulation

## Summary

This document defines the full-league Monte Carlo auction draft simulation framework for 12 teams.

The simulation now supports a perspective mode where any selected owner is treated as the focal owner (conceptually "Owner 1") while all other owners remain baseline-model controlled.

The implementation lives in:

- `etl/transform/monte_carlo_simulation.py`
- `etl/build_monte_carlo_simulation.py`

## Inputs

### Required

- PostgreSQL `draft_picks`
  - Historical draft outcomes used for owner behavior features.
- PostgreSQL `players` / `player_seasons`
  - Draftable player pool and active positions.
- PostgreSQL `draft_values`
  - Player value features and desirability scores.

### Optional

- PostgreSQL `draft_budgets`
  - Owner budgets; fallback budget is used when missing.

## League Rules Encoded

Default rule set:

- Teams: 12
- Roster size: 16
- Min bid: 1
- Position limits:
  - QB: 2
  - RB: 5
  - WR: 5
  - TE: 2
  - DEF: 1
  - K: 1

All values are configurable via `SimulationConfig` or CLI arguments.

## Simulation Assumptions

### Bidding logic

Each owner computes a bid ceiling per nominated player from:

- Base player value (`predicted_auction_value`)
- Projected points
- Position need pressure
- Owner position affinity (historical spend + count share)
- Repeated-player tendency bonus (historical repeat drafts)
- Controlled random volatility

### Tie-breaking

- If multiple owners tie at top bid value, winner is random among tied owners.

### Nomination logic

- Round-robin nomination over owners.
- Owner order is shuffled each iteration.
- Nominator draws from a top desirability pool for realism and variance.

### Stopping rules

Simulation iteration ends when:

- All teams reach roster size, or
- Player pool is exhausted.

## Constraints Enforced

- No owner can exceed budget.
- No owner can exceed roster size.
- No owner can exceed configured position limits.
- A player can only be drafted once per iteration.

## Outputs

Running the CLI writes:

- `draft_picks.csv`
  - Per iteration pick log (owner, player, price, nominator, points/value fields).
- `team_metrics.csv`
  - Per iteration per team outcomes:
    - roster composition size
    - total spend and spend by position
    - projected points
    - value captured vs expected value
- `owner_summary.csv`
  - Aggregated OwnerID-focused metrics, including OwnerID = 1 expected outcomes.
- `assumptions.json`
  - Machine-readable assumptions and rule settings.
- `owner_points_distribution.json`
  - Distribution percentiles for OwnerID target points.

## Perspective Owner Strategy View

Perspective-owner outputs include:

- Expected total points
- Expected spend by position
- Expected value captured
- Probability snapshot of landing top key targets

The focal owner can apply request-time strategy knobs (without persisting settings):

- `aggressiveness_multiplier`
  - Scales how much the owner overspends or underspends versus predicted value.
- `position_weights`
  - Position-specific multipliers (for example, raising RB spend pressure while reducing WR pressure).
- `risk_tolerance`
  - Controls bid volatility tolerance for the focal owner.
- `player_reliability_weight`
  - Raises or lowers preference for players with stronger reliability signals.

These outputs provide immediate hooks for:

- notebook analytics
- backend API exposure
- dashboard visualization tools

## CLI Usage

Run from repository root:

```bash
python -m etl.build_monte_carlo_simulation \
  --iterations 2000 \
  --seed 42 \
  --target-owner-id 1 \
  --teams-count 12 \
  --roster-size 16 \
  --league-id 1 \
  --output-dir backend/data/simulation
```

## Configuration Options

`SimulationConfig` supports:

- `iterations`
- `seed`
- `target_owner_id`
- `teams_count`
- `roster_size`
- `min_bid`
- `nomination_pool_size`
- `budget_fallback`
- `strategy_aggressiveness`
- `owner_position_noise`
- `owner_player_repeat_bonus`
- `target_key_players`
- `position_limits`
- `focal_owner_id`
- `focal_aggressiveness_multiplier`
- `focal_position_weights`
- `focal_risk_tolerance`
- `focal_player_reliability_weight`

## Limitations

- Historical owner behavior is modeled from available draft results only.
- Position scarcity and value are only as strong as source ranking quality.
- If seasonal valuation rows are unavailable in `draft_values`, projected points are proxy-derived.
- Current strategy toggles are OwnerID-centric but can be extended to multi-owner strategy scenarios.

---

## ML Feature Bridge (Issue #107)

The simulation engine now accepts rankings derived from the ML feature pipeline
(Issue #106) when available, with a local fallback feature computation path,
instead of the legacy `draft_values` table.

### Integration Module

`etl/transform/ml_feature_bridge.py` — converts outputs of
`compute_player_draft_features()` and `compute_draft_season_features()` (or the
local fallback feature implementations when Issue #106 modules are unavailable) into
the `historical_rankings_df` format required by `run_monte_carlo_draft_simulation()`.

#### Feature mapping

| ML Feature (Issue #106) | Simulation Input |
|---|---|
| `draft_avg_cost` | `predicted_auction_value` (floored at 1.0) |
| `bargain_score` (positive component × avg_cost × 0.5) | `model_score` |
| `bidding_war_likelihood` CV (inverted: 1 − CV) | `consistency` → `player_reliability_score` |
| `inflation_index` from `draft_season_features` (mean across positions) | applied as a multiplier to `predicted_auction_value` |

#### Temporal leakage guard

`build_simulation_rankings(target_season=N)` filters `player_features` to
`season_year < N`, then takes each player's **most recent prior season** row.
This ensures the simulation never observes data from the season being drafted.

#### CLI usage with ML features

```bash
python -m etl.build_monte_carlo_simulation \
  --iterations 2000 \
  --seed 42 \
  --target-owner-id 1 \
  --league-id 1 \
  --use-ml-features \
  --target-season 2026 \
  --output-dir backend/data/simulation
```

Without `--use-ml-features`, the legacy `draft_values` table is used (default
behaviour for backward compatibility).

### Invariant guarantees

The ML feature bridge preserves all existing simulation invariants:

- `predicted_auction_value ≥ 1.0` for all players
- `model_score ≥ 0.0` (negative bargain is clamped to zero)
- `consistency ∈ [0, 1]` (CV clamped at 1.0; None/NaN → 0.5 neutral)

## Definition of Done Mapping

- Full-league Monte Carlo simulation implemented and runnable: ✅
- Inputs and assumptions documented: ✅
- Metrics aggregated with OwnerID=1 view: ✅
- Output hooks for notebooks/backend/analyzer: ✅
- ML feature bridge connecting Issue #106 outputs to simulation: ✅