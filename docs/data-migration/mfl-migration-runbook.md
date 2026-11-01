# MFL Migration Runbook

Status: Draft for Issue #260

## Purpose

Operational guide for migrating historical MFL data into app tables with auditable checkpoints.

Workflow:

1. Extract from MFL API to CSV.
2. Validate with dry-run import.
3. Apply import.
4. Reconcile source vs database counts.
5. Rerun/backfill when mismatches are found.

## Prerequisites

- Backend environment is configured and database is reachable.
- Target app league id is known.
- For private leagues, an MFL session cookie is available.

### Retained PPL databases: remediation gate (Refs #524–#528)

The existing Post Pacific League app/staging databases are not a clean
replay of the migration graph. Do not run the archival `load_ppl_history.py`
loader or apply an import to these originals. Its numeric-ID assumptions and
account mutations are not an identity-remediation strategy.

Before the standard import flow:

1. Retain verified backups of both databases and restore distinct working
   copies with database names beginning `ffpi_528_`. Keep originals unchanged.
2. Set `PPL_TARGET_DATABASE_URL` and `PPL_STAGING_DATABASE_URL` privately to
   those copies. Do not put credentialed URLs in shell history, reports or Git.
3. Reconcile retained bootstrap CSVs against staging and the app schema:

   ```powershell
   python -m backend.scripts.reconcile_ppl_history `
     --source-root backend\data `
     --target-league-id 60 `
     --output C:\restricted-reports\ppl-reconciliation.json
   ```

   The command uses read-only repeatable-read transactions, accepts only named
   working copies, and refuses to overwrite an existing report. Exit code **2**
   means the report was saved but import remains blocked; **1** indicates an
   operational/input failure. Argument errors also use argparse's exit code 2
   without a saved-report message.
4. Review source SHA-256 hashes, full draft multisets (season, owner, player,
   exact bid, position and team), conflicting source IDs, missing attributes,
   observed schema fingerprint, unknown Alembic revisions and uniqueness drift.
   Tables/columns alone cannot prove schema compatibility.
5. Use the report's `mapping_review_template` as an **unapproved** review
   worksheet. Supply explicit source-player to canonical-player mappings and
   `(season, source_owner_id)` to target-owner mappings, each supported by
   evidence. Name matches and overlapping numeric IDs are candidates only;
   they must not become automatic approvals or cross-season fallbacks.
6. Resolve source discrepancies and event grain, then design reviewed schema
   adoption and test ingestion/idempotency/runtime behavior on copies. An
   unknown revision must not be blindly stamped or replaced by an invented
   migration. Preserve existing source-event, platform-ID and historical-stub
   fields when reconciling the schema.

This read-only report is not an importer or a completed #528 certification.
Keep reports and identity-review evidence in access-restricted storage outside
Git; publish aggregate findings only. The general flows below do not bypass
this remediation gate.

Optional checks:

- `python -m backend.manage extract-mfl-history --help`
- `python -m backend.manage import-mfl-csv --help`
- `python -m backend.manage reconcile-mfl-import --help`
- Review `mfl-extraction-matrix.md` before adding a new report family.
- Update `mfl-year-status-matrix.md` and `mfl-test-results-log.md` after each extraction pass.

## Standard Migration Flow (API-Available Seasons)

Example season range: 2004-2026.

1. Extract CSV and raw JSON:

```bash
python -m backend.manage extract-mfl-history \
  --start-year 2004 \
  --end-year 2026 \
  --output-root exports/history
```

2. Dry-run import validation:

```bash
python -m backend.manage import-mfl-csv \
  --input-root exports/history \
  --target-league-id <APP_LEAGUE_ID> \
  --start-year 2004 \
  --end-year 2026
```

3. Apply import:

```bash
python -m backend.manage import-mfl-csv \
  --input-root exports/history \
  --target-league-id <APP_LEAGUE_ID> \
  --start-year 2004 \
  --end-year 2026 \
  --apply
```

4. Reconcile source CSV vs imported rows:

```bash
python -m backend.manage reconcile-mfl-import \
  --input-root exports/history \
  --target-league-id <APP_LEAGUE_ID> \
  --start-year 2004 \
  --end-year 2026 \
  --output-json reports/mfl-reconciliation-2004-2026.json
```

5. Review reconciliation output:

- `mismatch_count` should be zero for clean migration.
- `season_reports[].mismatches` should be empty.
- `warnings` should contain only expected file-gap notes (if any).

## Legacy Fallback Flow (2002-2003)

Use this when extraction fails due unresolved legacy host redirects.

1. Scaffold manual templates:

```bash
python -m backend.manage scaffold-mfl-manual-csv \
  --start-year 2002 \
  --end-year 2003 \
  --output-root exports/history_manual
```

2. Fill CSVs:

- `exports/history_manual/franchises/2002.csv`
- `exports/history_manual/franchises/2003.csv`
- `exports/history_manual/players/2002.csv`
- `exports/history_manual/players/2003.csv`
- `exports/history_manual/draftResults/2002.csv`
- `exports/history_manual/draftResults/2003.csv`

Required metadata conventions:

- `source_system=mfl`
- `source_endpoint=manual_csv`
- `extracted_at_utc=<ISO-8601 UTC timestamp>`

3. Dry-run import:

```bash
python -m backend.manage import-mfl-csv \
  --input-root exports/history_manual \
  --target-league-id <APP_LEAGUE_ID> \
  --start-year 2002 \
  --end-year 2003
```

4. Apply import:

```bash
python -m backend.manage import-mfl-csv \
  --input-root exports/history_manual \
  --target-league-id <APP_LEAGUE_ID> \
  --start-year 2002 \
  --end-year 2003 \
  --apply
```

5. Reconcile manual seasons:

```bash
python -m backend.manage reconcile-mfl-import \
  --input-root exports/history_manual \
  --target-league-id <APP_LEAGUE_ID> \
  --start-year 2002 \
  --end-year 2003 \
  --output-json reports/mfl-reconciliation-2002-2003.json
```

## Rerun And Backfill Strategy

If reconciliation reports mismatches:

1. Identify seasons with non-empty `mismatches`.
2. Re-run extraction for only affected season(s) and report type(s).
3. Re-run dry-run import for affected season(s).
4. Apply import for corrected data.
5. Re-run reconciliation for affected season(s) only.

Recommended narrow-scope rerun examples:

```bash
python -m backend.manage extract-mfl-history --start-year 2014 --end-year 2014 --report-types players,draftResults --output-root exports/history
python -m backend.manage import-mfl-csv --input-root exports/history --target-league-id <APP_LEAGUE_ID> --start-year 2014 --end-year 2014
python -m backend.manage import-mfl-csv --input-root exports/history --target-league-id <APP_LEAGUE_ID> --start-year 2014 --end-year 2014 --apply
python -m backend.manage reconcile-mfl-import --input-root exports/history --target-league-id <APP_LEAGUE_ID> --start-year 2014 --end-year 2014 --output-json reports/mfl-reconciliation-2014.json
```

## Artifacts To Retain

- Extraction summary: `exports/history/_run_summary.json`.
- Raw source payloads: `exports/history/raw/<report_type>/<season>.json`.
- Reconciliation outputs under `reports/`.
- HTML page snapshots or parsed extracts for `options?O=` reports when API export is not the source.

## Documentation Discipline

After any meaningful extraction test:

1. Update `mfl-year-status-matrix.md` for the impacted season(s).
2. Record exact commands, URLs, and artifacts in `mfl-test-results-log.md`.
3. If a new page/report is introduced, add it to `mfl-extraction-matrix.md` with its primary method and fallback path.

These artifacts support reproducibility and audit review for any season-level corrections.