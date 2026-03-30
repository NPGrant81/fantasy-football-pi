# Artifact 01: Canonicalization Quality Gates (#103)

## Gate Checks
- Idempotency digest matches across consecutive runs.
- Output row totals are consistent (`total_rows`, `unique_player_ids`, `deduplicated_rows`).
- Position distribution is emitted and reviewable from `position_distribution`.
- Duplicate canonical-name keys are emitted and reviewable from `duplicate_name_keys`.

## Fallback Policy
If critical fields are missing, fail closed with explicit error (`Missing required columns`).

## Evidence to Post
- Run digest
- Input/output row counts
- Position distribution summary
- Duplicate canonical-name-key summary
