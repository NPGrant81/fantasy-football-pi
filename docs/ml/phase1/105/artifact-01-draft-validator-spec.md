# Artifact 01: Historical Draft Validator Spec (#105)

## Goal
Validate historical draft rows for key integrity before model features and post-draft analysis consume them.

## Inputs
- Draft results with at minimum:
  - `PlayerID`
  - `OwnerID`
  - `Year`
  - `PositionID`
  - `TeamID`
  - `WinningBid`
- Optional reference datasets:
  - players (`Player_ID`)
  - owners (`OwnerID`)
  - positions (`PositionID`)

## Validation Rules
1. Enforce required columns for draft rows and reference datasets.
2. Flag invalid/missing references for `PlayerID`, `OwnerID`, and `PositionID`.
3. Flag invalid or null `Year`.
4. Flag invalid or negative `WinningBid`.
5. Identify duplicate `(Year, OwnerID, PlayerID)` tuples and emit correction-ledger rows.
6. Emit validated rows, correction ledger, and aggregate validation report.
7. Pick-slot completeness checks by (`league_id`, `round_num`, `pick_num`) are out of current scope.

## Output Contract
- Validated draft rows with normalized numeric keys.
- Correction ledger rows for duplicate-key candidates.
- Aggregated report with source row counts, error counts, duplicate-key counts, and error breakdown.
