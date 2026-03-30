# Artifact 01: Canonicalization Quality Gates (#103)

## Gate Checks
- Idempotency digest matches across consecutive runs.
- Position resolution percentage meets minimum target (>= 99% for fantasy-active positions).
- Merge/split counts are reported and non-negative.
- Unresolved alias count is tracked and non-negative.

## Fallback Policy
If critical fields are missing, fail closed with explicit error (`Missing required columns`).

## Evidence to Post
- Run digest
- Input/output row counts
- Position resolution percentage
- Merge/split summary
- Unresolved alias count
