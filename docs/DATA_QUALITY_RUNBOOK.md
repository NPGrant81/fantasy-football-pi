# Data Quality Runbook

Date: 2026-03-19
Scope: Data-quality guardrails for historical ingest, normalization, and standings-consumer reliability.

## What Is Implemented

### Guardrail Modules
- `backend/tests/test_data_quality_guardrails.py`
- `backend/tests/test_data_quality_seasonal_guardrails.py`
- `backend/tests/test_data_quality_volume_guardrails.py`

### Coverage Areas
- Schema contract stability for normalized records.
- Core-field completeness thresholds.
- Freshness and timestamp sanity checks.
- Cross-table reconciliation (standings vs matchups).
- Referential consistency for ownership/transaction records.
- ETL idempotency and change-boundary behavior.
- Seasonal continuity and playoff boundary checks.
- Load-volume anomaly detection (delta, z-score, minimum rows).

## How To Run

### Targeted Guardrail Suite
From repository root:

```powershell
$env:TESTING='1'
$env:DATABASE_URL='sqlite:///./pytest_backend.db'
python3.13.exe -m pytest backend/tests/test_data_quality_guardrails.py backend/tests/test_data_quality_seasonal_guardrails.py backend/tests/test_data_quality_volume_guardrails.py
```

### Full Backend Suite
From repository root:

```powershell
$env:TESTING='1'
$env:DATABASE_URL='sqlite:///./pytest_backend.db'
python3.13.exe -m pytest backend/tests
```

## Failure Interpretation Matrix

### Schema Drift
- Tests:
  - `test_extract_players_schema_guardrail_has_required_columns`
- Signal:
  - Required normalized columns disappeared or renamed.
- Likely Causes:
  - Upstream payload shape changed.
  - Normalizer refactor dropped fields.
- First Actions:
  1. Inspect current source payload for field-path changes.
  2. Compare normalizer output keys before/after.
  3. Update mapper aliases and add fixture covering new shape.

### Completeness Thresholds
- Tests:
  - `test_extract_players_completeness_guardrail_for_core_fields`
- Signal:
  - Too many rows missing key identity attributes.
- Likely Causes:
  - Partial upstream responses.
  - Incorrect fallback path logic.
- First Actions:
  1. Sample failed rows to find dominant missing field.
  2. Validate fallback extraction logic for that field.
  3. If source degradation is real, lower threshold only with explicit rationale.

### Freshness / Time Sanity
- Tests:
  - `test_extract_players_freshness_guardrail_extracted_at_not_future`
  - `test_transaction_freshness_guardrail_detects_future_timestamps`
- Signal:
  - Extracted timestamps are in the future or transaction times are implausible.
- Likely Causes:
  - Clock skew.
  - Naive/aware timezone conversion bugs.
- First Actions:
  1. Verify system timezone and NTP sync.
  2. Normalize all persisted/comparison timestamps to UTC.
  3. Add explicit conversion at ingest boundaries.

### Cross-Table Reconciliation
- Tests:
  - `test_standings_reconcile_with_completed_matchups`
- Signal:
  - PF/PA totals or W/L balance no longer reconcile with completed matchup facts.
- Likely Causes:
  - Standings query scope drift.
  - Incomplete matchup filtering.
- First Actions:
  1. Compare query predicates for standings and source matchups.
  2. Verify completed-only filtering is applied consistently.
  3. Add a regression fixture for the discovered mismatch pattern.

### Referential Consistency
- Tests:
  - `test_transaction_history_referential_guardrail_detects_cross_league_owner`
  - `test_ownership_chain_guardrail_detects_owner_transitions_out_of_order`
- Signal:
  - Ownership references cross league boundaries or chain transitions are broken.
- Likely Causes:
  - Write path bypassed league validation.
  - Backfill imported unordered/malformed transaction rows.
- First Actions:
  1. Trace writes for transaction creation path.
  2. Enforce league ownership checks before insert.
  3. Reorder/fix source rows in backfill when timestamps are out-of-order.

### ETL Idempotency / Change Boundary
- Tests:
  - `test_load_normalized_html_is_idempotent_for_existing_rows`
  - `test_load_normalized_html_inserts_when_row_payload_changes`
- Signal:
  - Re-running identical load inserts duplicates, or changed payload fails to insert new row.
- Likely Causes:
  - Fingerprint instability.
  - Incorrect duplicate lookup keys.
- First Actions:
  1. Compare fingerprint inputs and key ordering.
  2. Verify `(dataset_key, row_fingerprint)` uniqueness behavior.
  3. Add fixture with minimally changed payload field.

### Seasonal Continuity / Playoff Boundary
- Tests:
  - `test_seasonal_week_coverage_guardrail_detects_gaps`
  - `test_playoff_boundary_guardrail_detects_early_playoff_week`
- Signal:
  - Missing regular-season weeks or playoff-marked games overlapping regular-season range.
- Likely Causes:
  - Partial ingest window.
  - Incorrect playoff flag mapping.
- First Actions:
  1. Re-check ingest date/week range filters.
  2. Validate source-to-model mapping for `is_playoff`.
  3. Backfill missing weeks before downstream standings recomputation.

### Volume Anomalies
- Tests:
  - `test_volume_guardrail_detects_large_season_over_season_drop`
  - `test_volume_guardrail_detects_large_season_over_season_spike`
  - `test_volume_guardrail_zscore_flags_outlier_dataset_count`
  - `test_volume_guardrail_required_dataset_thresholds_detect_missing_rows`
- Signal:
  - Row counts deviate sharply from baseline or required datasets fall below minimums.
- Likely Causes:
  - Source endpoint throttling.
  - Partial extraction/normalization runs.
  - Dataset key path moved.
- First Actions:
  1. Inspect run summary for failed/skipped files.
  2. Compare per-dataset counts against previous successful season.
  3. Re-run extraction for missing datasets and verify file presence.

## Escalation Levels
- P1:
  - Reconciliation failures affecting standings correctness.
  - Referential chain failures corrupting ownership state.
- P2:
  - Schema drift in high-volume datasets.
  - Severe volume anomalies (> 35% seasonal delta or > 3 sigma outlier).
- P3:
  - Threshold-only completeness warnings with stable downstream behavior.

## Update Policy
- Update this runbook whenever a new guardrail test module or threshold is introduced.
- Include the test name and a one-line operational remediation for every new guardrail.
- Keep thresholds in tests and this document synchronized.
