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

Optional checks:

- `python -m backend.manage extract-mfl-history --help`
- `python -m backend.manage import-mfl-csv --help`
- `python -m backend.manage reconcile-mfl-import --help`

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

These artifacts support reproducibility and audit review for any season-level corrections.