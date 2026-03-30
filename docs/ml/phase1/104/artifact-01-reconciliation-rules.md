# Artifact 01: Budget Timeline Reconciliation Rules (#104)

## Reconciliation Checks
- No nulls in required timeline fields.
- Remaining budget cannot be NaN.
- Remaining budget should not be negative.
- Outlier deltas (`abs(delta_budget) > start_budget`) are flagged.

## Metrics
- `reconciliation_pass_rate`
- `failed_rows`
- `negative_budget_rows`
- `null_rate_required_fields`
- `outlier_rows`

## Exception Queue
Rows with invalid owner mapping (`owner_id <= 0`) are emitted to `owner_mapping_exceptions`.

## Gate Policy
- Pass threshold default: `reconciliation_pass_rate >= 0.99`
- Any negative budget rows require manual review.
