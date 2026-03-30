# Artifact 01: Owner Budget Timeline Spec (#104)

## Goal
Build a deterministic owner-level budget timeline suitable for simulation and confidence-aware recommendation constraints.

## Inputs
- Event stream with at least:
  - `league_id`
  - `season`
  - `owner_id`
  - `event_ts`
  - `event_type`
  - either `delta_budget` or `winning_bid`

## Transform Rules
1. Parse and validate numeric owner/league/season keys.
2. Normalize event timestamps to UTC.
3. Derive `delta_budget` if absent from `winning_bid` (`delta = -winning_bid`).
4. Sort deterministically by (`league_id`, `season`, `owner_id`, `event_ts`, `event_type`).
5. Compute cumulative spend and remaining budget.

## Output Contract
- `league_id`, `season`, `owner_id`
- `event_ts`
- `event_type`
- `delta_budget`
- `spent_to_date`
- `remaining_budget`

## Determinism Guarantee
Identical input rows and start budget produce identical row order and cumulative values.
