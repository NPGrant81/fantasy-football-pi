# Data Migration Contracts

This folder defines source-to-target data contracts for migrating legacy league history into the app.

Primary tracker: GitHub Issue #256 (Define Data Requirements & Schemas)

## Documents

- `mfl-data-requirements.md`: Required report inventory, field-level contracts, source mapping, and open questions.
- `mfl-migration-runbook.md`: End-to-end operator workflow (extract, import, reconcile, rerun/backfill).
- `mfl-extraction-matrix.md`: Page/report inventory with preferred extraction method and fallbacks.
- `mfl-year-status-matrix.md`: Year-by-year extraction readiness and failure tracking.
- `mfl-test-results-log.md`: Test protocol, commands, artifacts, and observed outcomes.
- `mfl-html-records-normalization-plan.md`: Field mapping and transform contract for HTML champions/awards/records sources.

## Legacy Host Fallback

- For 2002-2003 seasons, do not assume API export is blocked. Public history/stat pages are reachable on `www47` and `www44`, and should be tested via HTML `options?O=` extraction before manual transcription fallback.
- Template scaffolding command:
  - `python -m backend.manage scaffold-mfl-manual-csv --start-year 2002 --end-year 2003`

## Scope

- Source platform: MyFantasyLeague (MFL) HTTP export API.
- Domain split:
  - Current-season operational data.
  - Historical analytics/archive data.

## Next issues in chain

- #257: Build extraction API/scripts (Legacy -> CSV)
- #258: Build import pipeline (CSV -> app)
- #259: Reconciliation and integrity checks
- #260: Workflow docs and rerun guidance (runbook added)