# Artifact 01: Historical Draft Validator Spec (#105)

## Goal
Validate historical draft rows for key integrity before model features and post-draft analysis consume them.

## Inputs
- Draft results with at minimum:
  - `league_id`
  - `year`
  - `owner_id`
  - `player_id`
  - `round_num`
  - `pick_num`
- Optional reference datasets:
  - players (`id`)
  - owners (`id`)

## Validation Rules
1. Enforce required key columns.
2. Flag missing critical references (`owner_id`, `player_id`, etc.).
3. Flag duplicate pick slots by (`league_id`, `year`, `round_num`, `pick_num`).
4. Optionally flag unknown owner/player references against supplied tables.
5. Emit `validation_status` and correction ledger entries for all issues.

## Output Contract
- Validated draft rows with normalized numeric keys.
- Validation status per row.
- Aggregated report with unresolved counts and year completeness.
- Correction ledger with row-level issue records.
