# MFL Historical Data Operations

This runbook defines the safest maintainable process for getting historical MFL data into PostgreSQL, archiving reproducible artifacts, restoring archived files when needed, and governing future updates.

## Goals

- Load historical data into PostgreSQL in a way that is repeatable, auditable, and reversible.
- Treat PostgreSQL as the application-serving source of truth.
- Treat generated files as recoverable working artifacts, not permanent primary storage.
- Preserve enough provenance to reproduce, investigate, or restore prior runs.
- Support future gap-filling for missing seasons, reports, or manual backfills without ad hoc cleanup.

## System Of Record

Use the following storage roles consistently:

- PostgreSQL tables are the canonical served data.
- `mfl_ingestion_runs` records operational run history.
- `mfl_ingestion_files` records per-file provenance, archive targets, checksums, and retention state.
- `mfl_html_record_facts` stores normalized historical HTML facts already loaded for app league `60`.
- `backend/exports/archive/` stores reproducible archived artifacts as zip files.
- `backend/exports/manifests/` stores human-readable archive manifests.
- Markdown docs are operating procedures and policy, not the authoritative dataset.

## Git Storage Policy

- Do not commit generated historical export roots (raw CSV/JSON/HTML, normalized roots, staged roots, or restore roots) to git.
- Generate these folders locally, then archive reproducible content with the archive commands.
- Keep archive zip and manifest artifacts in operational storage for retrieval and audit (local archive path, CI artifacts, or external object storage), not as routine git history payload.
- Commit code, schema, tests, runbooks, and issue-status evidence; treat large generated files as runtime artifacts.

## Safety Model

Follow this order for any load or update:

1. Extract into a dated or task-scoped export root.
2. Normalize or stage as needed.
3. Run dry-run validation first.
4. Apply the database load only after dry-run output is acceptable.
5. Archive reproducible raw/intermediate files after successful load.
6. Keep only the minimum working-set files in-place.
7. Preserve manifests and DB provenance for every archive action.

This order matters because it keeps data-serving writes separate from file cleanup, which lowers recovery risk.

## Recommended End-To-End Process

### 1. Extract Source Data

For HTML report families:

```powershell
python3.13.exe -m backend.manage extract-mfl-html-reports \
  --start-year 2002 \
  --end-year 2026 \
  --output-root backend/exports/history_html_records_2004_2026
```

For API CSV/JSON extraction, continue using the existing history extract flow already used in this repo.

Guidelines:

- Use a fresh export root when doing major reruns.
- Do not overwrite historical working folders unless the run is explicitly a replacement run.
- Keep manual scaffolds and manual probes separate from extracted roots.

### 2. Normalize Before Serving

For HTML records:

```powershell
python3.13.exe -m backend.manage normalize-mfl-html-records \
  --input-root backend/exports/history_html_records_2004_2026 \
  --output-root backend/exports/history_html_records_2004_2026_normalized
```

Guidelines:

- Normalize into a separate `_normalized` root.
- Treat normalized outputs as the preferred reload source.
- Keep normalized roots longer than raw/intermediate roots because they are smaller and directly useful.

### 3. Dry-Run The Database Load

For HTML fact loading:

```powershell
python3.13.exe -m backend.manage load-mfl-html-normalized \
  --input-roots backend/exports/history_html_records_2002_2003_normalized,backend/exports/history_html_records_2004_2026_normalized \
  --target-league-id 60
```

Expected behavior:

- Dry-run returns a `Run id`.
- Provenance is still written to `mfl_ingestion_runs` and `mfl_ingestion_files`.
- No fact-table writes are committed in dry-run mode.

Review before apply:

- warnings count
- files seen vs files loaded
- rows seen vs rows inserted vs rows skipped existing
- target league id, which should remain `60` for this migration path

### 3b. Compliance Gate For Draft Backfill Sheets

Before any `import-mfl-csv --apply` run that depends on manual draft overrides, validate the sheet-apply stage in dry-run mode:

```powershell
python3.13.exe -m backend.manage apply-mfl-draft-backfill-sheet \
  --input-root backend/exports/history_staged_2003 \
  --start-year 2003 \
  --end-year 2003 \
  --require-source-url
```

For any 2002 scope, keep the default 2002 source policy enabled. This policy requires `manual_source_url` and blocks known non-sourceable legacy feeds (`2002 O=17` and matching API draft endpoints).

Apply mode for sheet sync should only be used after dry-run summary shows zero policy skips for rows you intend to carry forward:

```powershell
python3.13.exe -m backend.manage apply-mfl-draft-backfill-sheet \
  --input-root backend/exports/history_staged_2003 \
  --start-year 2003 \
  --end-year 2003 \
  --require-source-url \
  --apply
```

### 4. Apply The Database Load

Apply only after dry-run looks correct:

```powershell
python3.13.exe -m backend.manage load-mfl-html-normalized \
  --input-roots backend/exports/history_html_records_2002_2003_normalized,backend/exports/history_html_records_2004_2026_normalized \
  --target-league-id 60 \
  --apply
```

Use `--truncate-before-load` only for intentional full replacement events, never for routine incremental updates.

### 5. Archive Reproducible File Artifacts

After a successful load, archive raw and intermediate artifacts.

HTML:

```powershell
python3.13.exe -m backend.manage archive-mfl-html-exports \
  --input-root backend/exports/history_html_records_2004_2026 \
  --apply \
  --prune-html
```

JSON:

```powershell
python3.13.exe -m backend.manage archive-mfl-json-exports \
  --input-root backend/exports/history_api_2023_2026 \
  --apply \
  --prune-json
```

CSV:

```powershell
python3.13.exe -m backend.manage archive-mfl-csv-exports \
  --input-root backend/exports/history_api_2023_2026 \
  --apply \
  --prune-csv
```

Archive policy:

- Archive raw HTML, raw JSON, staged CSV, and reproducible API CSV roots once loaded and verified.
- Keep normalized CSV roots in place by default.
- Keep manual backfill and manual probe roots until the missing-data gap is resolved or formally closed.

## Current Keep/Archive Policy

### Keep In Place

- `backend/exports/history_html_records_2002_2003_normalized`
- `backend/exports/history_html_records_2004_2026_normalized`
- `backend/exports/history_manual_draft_backfill`
- `backend/exports/history_probe_manual`

### Archive And Prune After Verification

- `history_api_*`
- `history_html_*` raw roots
- `history_staged_*`
- `history_quick`
- raw HTML/JSON/CSV working roots that can be regenerated from scripts or manifests

## Restore Procedure

Use the dedicated restore CLI and keep the restore path manifest-first.

### 1. Identify The Archive To Restore

- Open the relevant manifest in `backend/exports/manifests/`.
- Confirm the source root, archive zip, file list, checksum metadata, and archive run id.
- Optionally query `mfl_ingestion_runs` and `mfl_ingestion_files` for the same run id.

### 2. Restore Into A Separate Working Folder

Do not restore directly into the original root unless you are intentionally reconstructing that root.

Recommended pattern:

```powershell
python3.13.exe -m backend.manage restore-mfl-archive \
  --archive-path backend/exports/archive/history_api_2023_2026_csv.zip \
  --manifest-path backend/exports/manifests/history_api_2023_2026_csv_archive.json \
  --destination-root backend/exports/restore/history_api_2023_2026 \
  --apply
```

For HTML or JSON archives, swap the archive and manifest filenames accordingly.

### 3. Re-run Validation Or Load From The Restored Folder

Examples:

```powershell
python3.13.exe -m backend.manage normalize-mfl-html-records \
  --input-root backend/exports/restore/history_html_records_2004_2026
```

```powershell
python3.13.exe -m backend.manage load-mfl-html-normalized \
  --input-roots backend/exports/restore/history_html_records_2004_2026_normalized \
  --target-league-id 60
```

### 4. Restore Checklist

- Restore into a new folder first.
- Do not run `--truncate-before-load` during exploratory restore work.
- Compare restored file counts with the manifest.
- Use the manifest checksum list if file integrity is in doubt.
- Use `--overwrite-existing` only when intentionally replacing an older restore folder.

### 5. Restore Validation Process

Run a short restore validation cycle after introducing restore changes and during periodic operational checks.

Validation scope:

- One HTML archive restore in dry-run and apply mode.
- One JSON or CSV archive restore in dry-run and apply mode.
- One overwrite-existing apply run against a non-empty restore destination.

Recommended commands:

```powershell
python3.13.exe -m backend.manage restore-mfl-archive \
  --archive-path backend/exports/archive/history_api_2023_2026_json.zip \
  --manifest-path backend/exports/manifests/history_api_2023_2026_json_archive.json \
  --destination-root backend/exports/restore/history_api_2023_2026_json_smoke
```

```powershell
python3.13.exe -m backend.manage restore-mfl-archive \
  --archive-path backend/exports/archive/history_api_2023_2026_json.zip \
  --manifest-path backend/exports/manifests/history_api_2023_2026_json_archive.json \
  --destination-root backend/exports/restore/history_api_2023_2026_json_smoke \
  --apply
```

```powershell
python3.13.exe -m backend.manage restore-mfl-archive \
  --archive-path backend/exports/archive/history_api_2023_2026_json.zip \
  --manifest-path backend/exports/manifests/history_api_2023_2026_json_archive.json \
  --destination-root backend/exports/restore/history_api_2023_2026_json_smoke \
  --apply \
  --overwrite-existing
```

Expected outcomes:

- Dry-run reports matching manifest file counts and zero files restored.
- Apply restores all listed files with manifest verification enabled.
- Overwrite run completes successfully and replaces prior restore contents.

## Process For Future Missing Entries

When new missing seasons or data gaps are identified:

1. Create a new task-scoped export root rather than reusing an archived one.
2. Pull only the affected seasons, reports, or endpoints.
3. Normalize or stage only the impacted datasets.
4. Dry-run the load against PostgreSQL first.
5. Apply only the delta if the loader is idempotent for that dataset.
6. Archive the new raw/intermediate artifacts after verification.
7. Keep manual backfill CSVs only as long as they remain operationally necessary.

Recommended naming pattern:

- `backend/exports/history_api_2027_2027`
- `backend/exports/history_html_records_gapfill_2017`
- `backend/exports/history_manual_draft_backfill`

This keeps future work additive and easy to audit.

## PostgreSQL Serving Standard

Serve application reads from PostgreSQL tables, not from export files.

Operational standard:

- Files are for ingestion, audit, and restoration.
- PostgreSQL is for runtime application queries.
- The app should not rely on `backend/exports` being present in production for normal behavior.

## Governance Policies

### Change Control

- Any full reload or truncating replacement must be intentional and documented.
- Any archive command with pruning must be preceded by a successful load or explicit retention decision.
- Avoid deleting archives or manifests outside an approved cleanup pass.

### Data Quality

- Prefer dry-run first for every load.
- Use normalized data for reloads whenever possible.
- Keep manual datasets clearly separated and named as manual artifacts.
- Preserve source-vs-target identity boundaries:
  - source MFL league id remains source metadata
  - app serving target league id remains `60`

### Retention

- Retain normalized datasets longer than raw datasets.
- Retain manifests and DB provenance indefinitely unless a formal retention policy replaces them.
- Retain archives for reproducible historical reloads.

### Recoverability

- Never prune before the archive zip and manifest exist.
- Never restore directly over an active working root unless the intent is replacement.
- Keep archive filenames stable and one manifest per archive root.

### Documentation Discipline

- Update this runbook when commands or policy change.
- Update `docs/INDEX.md` when adding or renaming operational docs.
- When major migration decisions change, record the outcome in both this runbook and the relevant issue-status or project-management tracking doc.
- Record restore validation evidence (date, archive name, destination root, run id) in the active issue-status or project-management tracking doc.

## Operational Best Practices

- Use one logical run per concern: extract, normalize, load, archive.
- Prefer additive delta runs over monolithic reruns for future missing data.
- Query `mfl_ingestion_runs` and `mfl_ingestion_files` before assuming a file root is still active.
- Keep archive, manifest, and DB provenance aligned by run id.
- Do not treat markdown as the only record of what happened; rely on manifests plus DB provenance.

## Minimum Future Improvements

These are the next worthwhile hardening steps, but the current process is already safe and maintainable without them:

1. Add dedicated restore commands for HTML, JSON, and CSV archives.
2. Add checksum verification commands against archive manifests.
3. Add a small markdown template for post-run notes that references archive run ids.
4. Add CI checks that fail if large raw export roots are reintroduced without matching archive/manifests.

## Recommended Team Standard

The safest robust default for this project is:

- load into PostgreSQL from normalized datasets
- dry-run first, then apply
- archive reproducible raw/intermediate files immediately after verification
- keep normalized and manual-gapfill datasets in place until replacement policy is approved
- use manifests + ingestion tables for recovery, not ad hoc folder archaeology

That gives the project the best balance of safety, maintainability, reproducibility, and operational clarity.