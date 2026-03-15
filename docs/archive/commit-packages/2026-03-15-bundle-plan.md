# Commit Package Plan - 2026-03-15

This file captures the cleaned commit-package layout for the current working tree.

Important constraints:

- Bundle 1 is currently staged in the index for inspection.
- The historical MFL extraction work and MFL archive/restore work share `backend/manage.py`, so they must ship as one combined MFL bundle.
- Issues `#256` through `#260` already have prior completion updates on GitHub, so use `Refs #...` or `Follow-up for #...`, not `Closes #...`.
- The workflow/docs hygiene bundle maps best to `#270`, but that mapping is weaker than the others.

## Bundle 1 - Live Scoring Reliability

Current state:

- Already staged.

Inspect staged package:

```powershell
git diff --cached --stat
git diff --cached
```

Commit:

```powershell
git commit -m "feat(live-scoring): add resilient ingest diagnostics and watchdog controls" -m "Refs #264"
```

Re-stage from a clean index if needed:

```powershell
git reset
git add -- \
  backend/routers/admin_tools.py \
  backend/schemas/live_scoring.py \
  backend/schemas/__init__.py \
  backend/scripts/import_nfl_schedule.py \
  backend/services/live_scoring_contract.py \
  backend/services/live_scoring_ingest_service.py \
  backend/services/live_scoring_watchdog_service.py \
  backend/tests/test_admin_tools.py \
  backend/tests/test_live_scoring_contract.py \
  backend/tests/test_live_scoring_ingest_service.py \
  backend/tests/test_live_scoring_watchdog_service.py \
  docs/LIVE_SCORING_RELIABILITY_RUNBOOK.md
```

## Bundle 2 - MFL Historical Follow-up

Reset index, then stage:

```powershell
git reset
git add -- \
  .gitignore \
  backend/manage.py \
  backend/models.py \
  backend/scripts/extract_mfl_history.py \
  backend/scripts/extract_mfl_html_reports.py \
  backend/scripts/normalize_mfl_html_records.py \
  backend/scripts/load_mfl_html_normalized.py \
  backend/scripts/archive_mfl_html_exports.py \
  backend/scripts/archive_mfl_json_exports.py \
  backend/scripts/archive_mfl_csv_exports.py \
  backend/scripts/restore_mfl_archive.py \
  backend/scripts/stage_mfl_html_for_import.py \
  backend/tests/test_extract_mfl_history_draft_results.py \
  backend/tests/test_mfl_html_report_extract.py \
  backend/tests/test_normalize_mfl_html_records.py \
  backend/tests/test_archive_mfl_html_exports.py \
  backend/tests/test_archive_mfl_json_exports.py \
  backend/tests/test_archive_mfl_csv_exports.py \
  backend/tests/test_load_mfl_html_normalized.py \
  backend/tests/test_load_mfl_html_normalized_json_safe.py \
  backend/tests/test_restore_mfl_archive.py \
  backend/tests/test_stage_mfl_html_for_import.py \
  backend/tests/test_mfl_migration_scripts.py \
  db/migrations/0016_add_mfl_html_record_facts.py \
  db/migrations/0017_add_target_league_id_to_mfl_html_record_facts.py \
  db/migrations/0018_add_mfl_ingestion_metadata_tables.py \
  docs/INDEX.md \
  docs/MFL_HISTORICAL_DATA_OPERATIONS.md \
  docs/data-migration/README.md \
  docs/data-migration/mfl-data-requirements.md \
  docs/data-migration/mfl-migration-runbook.md \
  docs/data-migration/mfl-extraction-matrix.md \
  docs/data-migration/mfl-html-records-normalization-plan.md \
  docs/data-migration/mfl-test-results-log.md \
  docs/data-migration/mfl-year-status-matrix.md
```

Inspect:

```powershell
git diff --cached --stat
git diff --cached
```

Commit:

```powershell
git commit -m "feat(mfl): add historical load provenance plus archive and restore workflow" -m "Refs #256" -m "Refs #257" -m "Refs #258" -m "Refs #259" -m "Refs #260"
```

## Bundle 3 - Player Identity Dedupe

Reset index, then stage:

```powershell
git reset
git add -- backend/services/player_service.py
```

Inspect:

```powershell
git diff --cached --stat
git diff --cached
```

Commit:

```powershell
git commit -m "fix(players): prefer provider ids in canonical dedupe keys" -m "Refs #102"
```

## Bundle 4 - Workflow And Issue Hygiene Docs

Reset index, then stage:

```powershell
git reset
git add -- \
  CONTRIBUTING.md \
  docs/CLI_CHECKIN_LESSONS_LEARNED.md \
  docs/ISSUE_STATUS.md \
  docs/PR_NOTES.md \
  docs/BACKLOG_TRIAGE_2026-03-14.md \
  docs/archive/status-snapshots/2026-03-14/issue199_status.json \
  docs/archive/status-snapshots/2026-03-14/pr223_status.json \
  docs/archive/status-snapshots/2026-03-14/pr223_status_after_wait.json
```

Inspect:

```powershell
git diff --cached --stat
git diff --cached
```

Commit:

```powershell
git commit -m "docs(workflow): codify issue hygiene and archive stale status snapshots" -m "Refs #270"
```

## Leave Unstaged

These are currently just newline-only or formatting-only churn and should stay out unless intentionally grouped into a cleanup commit:

```text
backend/scripts/import_mfl_csv.py
backend/scripts/reconcile_mfl_import.py
backend/scripts/scaffold_mfl_manual_csv.py
```

## GitHub Comment Drafts

### Issue #264

```md
Status update: moving this issue toward completion with a staged reliability package.

Delivered in this follow-up:
- Added resilient live scoring ingest diagnostics with per-attempt fetch metadata.
- Added failover-aware ingest controls and admin endpoints for dry-run, health summary, and watchdog execution.
- Added durable JSONL ingest health logging and a reliability runbook.

Validation evidence:
- Targeted backend tests for live scoring contract, ingest service, watchdog service, and admin tools passed in local validation earlier in this workstream.

References:
- Planned commit: `feat(live-scoring): add resilient ingest diagnostics and watchdog controls`

Close-out note:
- If any remaining ESPN caching/replay tooling is still desired, that should be tracked separately from this reliability package.
```

### Issue #256

```md
Follow-up for historical MFL migration scope.

This package extends the original requirements/docs baseline with:
- corrected early-season host and league mapping evidence
- extraction matrix and year-by-year status tracking
- normalized HTML record dataset plan and execution log updates

References:
- Planned follow-up commit: `feat(mfl): add historical load provenance plus archive and restore workflow`

This should be treated as additional evidence and operator hardening tied to the original migration chain, not a second closure event.
```

### Issue #257

```md
Follow-up for extraction scope.

Additional extractor coverage now includes:
- corrected 2002/2003 league mapping behavior
- HTML `options?O=` extraction for records/history pages
- improved draft-results fallback handling for sparse seasons

References:
- Planned follow-up commit: `feat(mfl): add historical load provenance plus archive and restore workflow`
```

### Issue #258

```md
Follow-up for import pipeline scope.

This package adds the next operational layer around the import path:
- staging helper for importer-compatible MFL roots
- normalized HTML load path into PostgreSQL-backed historical fact storage
- target league provenance support for historical HTML facts

References:
- Planned follow-up commit: `feat(mfl): add historical load provenance plus archive and restore workflow`
```

### Issue #259

```md
Follow-up for reconciliation and integrity scope.

Additional integrity and auditability delivered in this package:
- ingestion run/file provenance tables
- archive manifests with checksums and archived-path tracking
- restore verification workflow and overwrite-path test coverage

References:
- Planned follow-up commit: `feat(mfl): add historical load provenance plus archive and restore workflow`
```

### Issue #260

```md
Follow-up for workflow documentation scope.

The migration workflow is now extended with:
- full historical operations runbook for extract -> normalize -> load -> archive -> restore
- explicit git storage policy for generated historical exports
- restore validation process and evidence expectations

References:
- Planned follow-up commit: `feat(mfl): add historical load provenance plus archive and restore workflow`
```

### Issue #102

```md
Status update: small follow-up fix prepared for player identity normalization.

Delivered:
- canonical player dedupe key now prefers stable provider ids (`gsis_id`, then `espn_id`) before falling back to display identity

Why this matters:
- reduces false merges when display identity is stable but provider identifiers are already available

References:
- Planned commit: `fix(players): prefer provider ids in canonical dedupe keys`
```

### Issue #270

```md
Status update: documentation/workflow follow-up package prepared.

Delivered in this docs bundle:
- issue status transition guidance
- branch/worktree lifecycle guidance
- stale status snapshot archival
- issue/PR note templates for consistent close-out hygiene

References:
- Planned commit: `docs(workflow): codify issue hygiene and archive stale status snapshots`

If this issue is meant to remain focused only on ESPN pipeline documentation, open a dedicated housekeeping/docs issue for this bundle instead of reusing #270.
```