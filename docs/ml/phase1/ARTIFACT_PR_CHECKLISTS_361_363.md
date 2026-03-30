# Phase 1 Artifact PR Checklists (Issues #361, #362, #363)

## Progress Snapshot (2026-03-29)
- #361 in progress: initial transform module, alias map, and docs landed.
- #362 in progress: initial timeline transform and reconciliation docs landed.
- #363 in progress: initial draft validator transform and ledger schema docs landed.
- Initial ETL output files from real data runs are committed under `etl/outputs/**` as provisional artifacts; gate evidence rollup back to issue #360 remains pending.

## Issue #361 (Implements #103)
### Deliverable file targets
- docs/ml/phase1/103/artifact-01-canonicalization-spec.md
- docs/ml/phase1/103/artifact-01-quality-gates.md
- etl/transform/player_metadata_canonicalization.py
- etl/transform/player_metadata_alias_map.yml
- etl/outputs/player_metadata/canonical_players_v1.csv
- etl/outputs/player_metadata/canonicalization_report_v1.json

### Required validation outputs
- Idempotency check from two consecutive runs.
- PositionID resolution percentage for active players.
- Merge/split counts and low-confidence queue size.
- Drift summary versus prior baseline.

## Issue #362 (Implements #104)
### Deliverable file targets
- docs/ml/phase1/104/artifact-01-budget-timeline-spec.md
- docs/ml/phase1/104/artifact-01-reconciliation-rules.md
- etl/transform/owner_budget_timeline.py
- etl/outputs/owner_budget/budget_timeline_v1.csv
- etl/outputs/owner_budget/budget_timeline_report_v1.json

### Required validation outputs
- Reconciliation pass rate and failed owner-year rows.
- Unresolved OwnerID count and exception queue summary.
- Null-rate for required timeline fields.
- Outlier detection summary.

## Issue #363 (Implements #105)
### Deliverable file targets
- docs/ml/phase1/105/artifact-01-draft-validator-spec.md
- docs/ml/phase1/105/artifact-01-correction-ledger-schema.md
- etl/transform/historical_draft_validator.py
- etl/outputs/draft_validation/validated_draft_results_v1.csv
- etl/outputs/draft_validation/draft_validation_report_v1.json
- etl/outputs/draft_validation/draft_correction_ledger_v1.csv

### Required validation outputs
- Critical unresolved reference count by type.
- Year completeness summary for in-scope years.
- Duplicate and missing pick counts.
- Keeper labeling summary and confidence notes.

## Rollup Gate Rule
For each artifact PR, include validation evidence in the PR body and link evidence back to issue #360 phase gate tracking.
