# CSV Source-of-Truth Retirement Matrix

Status: Active execution matrix for issue #365 follow-through after Critical and High completion.

## Scope

Parent issue:
- #365 Eliminate CSV source-of-truth dependencies (Critical -> Low triage)

Critical child issues:
- #366 Replace `import_mfl_csv` with Postgres-first source contracts
- #367 Retire CSV bootstrap path in `load_ppl_history`
- #368 Remove required CSV args from MFL bootstrap/import CLI

## Tier Status Snapshot

- Critical: complete for current phase.
- High: complete for current phase.
- Medium: complete for current phase.
- Low: complete for current phase.

## Completed Evidence (Critical + High)

| Tier | Item | Status | Evidence |
| --- | --- | --- | --- |
| Critical | Importer DB-only mode (`import-mfl-csv`) | Complete | `backend/scripts/import_mfl_csv.py`, `backend/manage.py` (`--source-mode` now DB-only; CSV runtime branch removed from CLI) |
| Critical | Legacy bootstrap archival-gated | Complete | `backend/scripts/load_ppl_history.py` dual opt-in guards |
| Critical | Franchise bootstrap DB-only mode | Complete | `backend/manage.py` (`bootstrap-mfl-franchise-users` now DB-only; auto-selects latest DB season when `--source-season` omitted; `--franchises-csv` removed) |
| High | Remove required CSV round-trip in active Phase 1 ETL path | Complete | `etl/build_phase1_artifacts.py` + DataFrame-native transform writers |

## Medium Tier Execution Matrix

### 1) `reconcile-mfl-import` source decoupling

| File | Current State | Gap | Action |
| --- | --- | --- | --- |
| `backend/scripts/reconcile_mfl_import.py` | Converted this pass | None for first medium target | Added DB source mode (`source_mode=db`) with dataset-key filtering + optional `source_league_id`; CSV mode retained as legacy |
| `backend/manage.py` (`reconcile-mfl-import`) | Converted this pass | None for first medium target | `--source-mode` is now DB-only; `--source-league-id` retained; CSV CLI args removed |
| `backend/tests/test_mfl_migration_scripts.py` | Converted this pass | None for first medium target | Added DB-mode reconcile regression coverage |
| `backend/tests/test_manage_import_mfl_csv_cli.py` | Converted this pass | None for first medium target | Added CLI coverage for DB mode and CSV mode guardrail |

Validation command:
- `python3.13.exe -m pytest backend/tests/test_mfl_migration_scripts.py backend/tests/test_manage_import_mfl_csv_cli.py`

Result:
- PASS (10 tests)

### 2) Staging utility DB contract migration

| File | Current State | Gap | Planned Action |
| --- | --- | --- | --- |
| `backend/scripts/stage_mfl_html_for_import.py` | Converted this pass | None for stage first medium target | Added DB source mode (`source_mode=db`, default path) with optional `source_league_id`; CSV mode retained as legacy |
| `backend/manage.py` (`stage-mfl-html-for-import`) | Converted this pass | None for stage first medium target | `--source-mode` is now DB-only; `--source-league-id` retained; CSV CLI args removed |
| `backend/tests/test_stage_mfl_html_for_import.py` | Converted this pass | None for stage first medium target | Added DB-mode staging and source-league filter coverage |
| `backend/tests/test_manage_import_mfl_csv_cli.py` | Converted this pass | None for stage first medium target | Added stage CLI DB mode and CSV guardrail coverage |

### 3) Draft backfill workflow DB contract migration

| File | Current State | Gap | Planned Action |
| --- | --- | --- | --- |
| `backend/scripts/prepare_mfl_draft_backfill_sheet.py` | Converted this pass | None for prepare first medium target | Added DB source mode (`source_mode=db`, default path) with optional `source_league_id`; CSV mode retained as legacy |
| `backend/manage.py` (`prepare-mfl-draft-backfill-sheet`) | Converted this pass | None for prepare first medium target | `--source-mode` is now DB-only; `--source-league-id` retained; CSV CLI args removed |
| `backend/tests/test_stage_mfl_html_for_import.py` | Converted this pass | None for prepare first medium target | Added DB-mode prepare backfill coverage |
| `backend/tests/test_manage_import_mfl_csv_cli.py` | Converted this pass | None for prepare first medium target | Added prepare CLI DB mode and CSV guardrail coverage |
| `backend/scripts/resolve_mfl_draft_backfill_names.py` | Converted this pass | None for resolve first medium target | Added DB source mode (`source_mode=db`, default path) with optional `source_league_id`; CSV mode retained as legacy |
| `backend/manage.py` (`resolve-mfl-draft-backfill-names`) | Converted this pass | None for resolve first medium target | `--source-mode` is now DB-only; `--source-league-id` retained; CSV CLI args removed |
| `backend/tests/test_stage_mfl_html_for_import.py` | Converted this pass | None for resolve first medium target | Added DB-mode resolve backfill coverage |
| `backend/tests/test_manage_import_mfl_csv_cli.py` | Converted this pass | None for resolve first medium target | Added resolve CLI DB mode and CSV guardrail coverage |
| `backend/scripts/apply_mfl_draft_backfill_sheet.py` | Converted this pass | None for apply first medium target | Added DB source mode (`source_mode=db`, default path) that updates matching draft fact rows in `mfl_html_record_facts`; CSV mode retained as legacy |
| `backend/manage.py` (`apply-mfl-draft-backfill-sheet`) | Converted this pass | None for apply first medium target | `--source-mode` is now DB-only; `--source-league-id` retained; CSV CLI args removed |

Guardrail hardening (historical):
- Migration/backfill commands previously required explicit acknowledgment for CSV mode during transition.
- Current state: CSV runtime branches have been removed from `import-mfl-csv`, `reconcile-mfl-import`, `stage-mfl-html-for-import`, `prepare-mfl-draft-backfill-sheet`, `resolve-mfl-draft-backfill-names`, and `apply-mfl-draft-backfill-sheet` command surfaces.
- Current state: `bootstrap-mfl-franchise-users` no longer supports `--franchises-csv`; DB source facts are required.
- `scaffold-mfl-manual-csv` now requires explicit legacy acknowledgment: `--allow-legacy-csv-source`.
- `backend/scripts/import_scoring_rules.py` CLI is now archival-gated with dual opt-in (`FFPI_ALLOW_LEGACY_CSV_ARCHIVE=1` + `--allow-legacy-csv-archive`).
- `archive-mfl-csv-exports` now requires explicit legacy acknowledgment: `--allow-legacy-csv-source`.

Workflow reduction (this pass):
- Added one-step `normalize-load-mfl-html-records` command in `backend/manage.py` that runs HTML normalization + DB load with a temporary intermediate normalized root by default.
- This makes persistent normalized CSV directories optional for operator workflows.
- P1 complete: direct `load-mfl-html-normalized` and `normalize-mfl-html-records` CLI commands removed from `backend/manage.py`.
- Documentation alignment completed for current operations/runbook surfaces so one-step normalize+load is the supported operator path.
| `backend/tests/test_stage_mfl_html_for_import.py` | Converted this pass | None for apply first medium target | Added DB-mode apply backfill coverage |
| `backend/tests/test_manage_import_mfl_csv_cli.py` | Converted this pass | None for apply first medium target | Added apply CLI DB mode and CSV guardrail coverage |

### 4) Reconcile+backfill orchestration docs/CLI updates

| Area | Current State | Gap | Planned Action |
| --- | --- | --- | --- |
| `docs/data-migration/mfl-migration-runbook.md` | CSV-centric command examples | Needs DB-first examples for medium tools | Add DB-first flows + explicit legacy CSV examples |
| `backend/manage.py` command help text | Mixed | Some medium commands still imply CSV-first usage | Mark CSV arguments as legacy where DB mode exists |

## Low Tier Execution (P2)

| File | Current State | Disposition |
| --- | --- | --- |
| `backend/scripts/seed_scoring_rules.py` | Removed | Deleted from repository |
| `backend/scripts/seed_draft_budgets.py` | Removed | Deleted from repository |
| `backend/scripts/ingest_data.py` | Removed | Deleted from repository |
| `backend/scripts/init_league.py` | Removed | Deleted from repository |
| `backend/scripts/import_scoring_logic.py` | Removed | Deleted from repository |
| `backend/tests/test_legacy_csv_script_gates.py` | Removed | Obsolete archival-gate suite deleted with scripts |

Latest validation command:
- `python3.13.exe -m pytest backend/tests/test_manage_normalize_load_mfl_html_records_cli.py backend/tests/test_manage_normalize_mfl_html_records_cli.py backend/tests/test_manage_load_mfl_html_normalized_cli.py backend/tests/test_manage_import_mfl_csv_cli.py backend/tests/test_manage_bootstrap_mfl_franchise_users_cli.py`

Result:
- PASS (22 tests) for P1/P2 command-surface + retirement follow-up.

## Next Implementation Order

1. Run optional historical docs cleanup to remove references to deleted legacy scripts from non-migration docs.

## Exit Criteria (remaining from #365)

- Medium tools can run from DB source contracts without required local CSV roots.
- Remaining CSV usage is optional diagnostic output or user-facing import/export UX.
- Legacy scripts are explicitly gated as archival-only or removed from active runtime pathways.
