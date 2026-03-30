# Artifact 01: Owner Budget Timeline Spec (#104)

## Goal
Build a deterministic owner-level budget timeline suitable for simulation and confidence-aware recommendation constraints.

## Inputs
- Draft budget dataset with at least:
  - `OwnerID`
  - `Year`
  - `DraftBudget`
- Draft results dataset with at least:
  - `OwnerID`
  - `Year`
  - `PlayerID`
  - `WinningBid`
- Users dataset with at least:
  - `OwnerID`
  - `OwnerName`

## Transform Rules
1. Parse and validate numeric owner/year keys and dollar values.
2. Use deterministic event order from source-row `event_sequence`.
3. Resolve starting budget by precedence: exact year, carry-forward prior year, carry-backward future year, then global default.
4. Compute cumulative spend and remaining budget from `WinningBid`.
5. Emit reconciliation exceptions for imputed budgets and overspent owner-years.

## Output Contract
- `season_year`, `owner_id`, `owner_name`
- `event_sequence`
- `player_id`
- `winning_bid`
- `cumulative_spend`
- `starting_budget`
- `remaining_budget`
- `overspent`
- `budget_source`
- `source_season_year`

## Determinism Guarantee
Identical input datasets produce identical timeline row ordering and cumulative values.
