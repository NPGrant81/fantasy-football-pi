# Artifact 01: Budget Timeline Reconciliation Rules (#104)

## Reconciliation Checks
- Timeline rows are generated for valid owner/season bid events.
- Starting budgets are resolved via exact/year-carry/default strategy and tracked by source.
- Overspent owner-seasons are detected from negative remaining budget.
- Budget imputation and overspend events are recorded in `exceptions`.

## Metrics
- `timeline_rows`
- `owner_season_pairs`
- `overspent_owner_seasons`
- `budget_resolution_counts`
- `exceptions`

## Exception Queue
Exception records are emitted in the report `exceptions` list, including budget imputation (`budget_imputed`) and overspend (`overspent_budget`) events.

## Gate Policy
- Pass threshold default: `exceptions == 0` and `overspent_owner_seasons == 0`.
- Any owner-season overspend requires manual review.
