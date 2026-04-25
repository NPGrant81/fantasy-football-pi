"""Utility script for ad-hoc backend tasks.

Run `python -m backend.manage seed` to populate the database with the
default admin user + sample league. This replaces the previous startup
handler, eliminating the need for every test to trigger the seeder.
"""

from datetime import datetime, timezone

import click

from .core.security import get_password_hash
from .database import Base, SessionLocal, engine
from .scripts.audit_invalid_players import run_invalid_player_audit
from .scripts.audit_player_duplicates import run_audit as run_player_duplicate_audit
from .scripts.archive_mfl_csv_exports import run_archive_mfl_csv_exports
from .scripts.archive_mfl_json_exports import run_archive_mfl_json_exports
from .scripts.archive_mfl_html_exports import run_archive_mfl_html_exports
from .scripts.apply_mfl_draft_backfill_sheet import run_apply_mfl_draft_backfill_sheet
from .scripts.extract_mfl_history import run_mfl_history_extract
from .scripts.extract_mfl_html_reports import run_extract_mfl_html_reports
from .scripts.finalize_week import run_finalization
from .scripts.import_mfl_csv import run_import_mfl_csv
from .scripts.load_mfl_html_normalized import run_load_mfl_html_normalized
from .scripts.normalize_mfl_html_records import run_normalize_mfl_html_records
from .scripts.prepare_mfl_draft_backfill_sheet import run_prepare_mfl_draft_backfill_sheet
from .scripts.reconcile_mfl_import import run_reconcile_mfl_import
from .scripts.restore_mfl_archive import run_restore_mfl_archive
from .scripts.resolve_mfl_draft_backfill_names import run_resolve_mfl_draft_backfill_names
from .scripts.scaffold_mfl_manual_csv import run_scaffold_mfl_manual_csv
from .scripts.seed import run_seeder
from .scripts.stage_mfl_html_for_import import run_stage_mfl_html_for_import
from .scripts.validation.validate_mfl_import import run_validate_mfl_import, format_validation_output
from .scripts.validation.validate_season_hierarchy import run_validate_season_hierarchy, format_season_hierarchy_output
from .scripts.validation.validate_league_readiness import run_validate_league_readiness, format_league_readiness_output
import csv as _csv
import os as _os
from . import models


@click.group()
def cli():
    pass


@cli.command()
def seed():
    """Execute the auto-seeder using the session factory."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    print("Running seeder...")
    run_seeder(SessionLocal, get_password_hash)


@cli.command("audit-player-duplicates")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply merge/delete cleanup (default: audit only).")
@click.option("--fail-on-duplicates", is_flag=True, default=False, help="Exit non-zero when duplicates are detected.")
@click.option("--json-output", type=click.Path(dir_okay=False, writable=True), default=None, help="Optional path to write JSON report.")
def audit_player_duplicates(apply_changes: bool, fail_on_duplicates: bool, json_output: str | None):
    """Audit player duplicates and optionally clean them by re-pointing references."""
    summary = run_player_duplicate_audit(
        apply_changes=apply_changes,
        fail_on_duplicates=fail_on_duplicates,
        json_output=json_output,
    )

    click.echo("Player duplicate audit summary")
    click.echo(f"- Players checked: {summary['total_players_checked']}")
    click.echo(f"- Duplicate groups: {summary['duplicate_groups']}")
    click.echo(f"- Duplicate rows: {summary['duplicate_rows']}")

    if apply_changes:
        click.echo(f"- Rows merged: {summary['rows_merged']}")
        click.echo(f"- Rows touched: {summary['rows_touched']}")

    if fail_on_duplicates and summary["duplicate_groups"] > 0:
        raise click.ClickException(
            f"Found {summary['duplicate_groups']} duplicate player groups"
        )


@cli.command("audit-invalid-players")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply cleanup (default: audit only).")
@click.option("--allow-reset-draft-picks", is_flag=True, default=False, help="Allow setting draft_picks.player_id to NULL when no replacement exists.")
@click.option("--league-id", type=int, default=None, help="Scope cleanup to one league.")
@click.option("--owner-id", type=int, default=None, help="Scope cleanup to one owner ID.")
@click.option("--owner-team-name", type=str, default=None, help="Scope cleanup to one owner team name.")
@click.option("--json-output", type=click.Path(dir_okay=False, writable=True), default=None, help="Optional path to write JSON report.")
def audit_invalid_players(
    apply_changes: bool,
    allow_reset_draft_picks: bool,
    league_id: int | None,
    owner_id: int | None,
    owner_team_name: str | None,
    json_output: str | None,
):
    """Audit invalid placeholder players and optionally remap/reset references."""
    summary = run_invalid_player_audit(
        apply_changes=apply_changes,
        allow_reset_draft_picks=allow_reset_draft_picks,
        league_id=league_id,
        owner_id=owner_id,
        owner_team_name=owner_team_name,
        json_output=json_output,
    )

    click.echo("Invalid player audit summary")
    click.echo(f"- Invalid players with scoped refs: {summary['invalid_players_with_scoped_refs']}")
    click.echo(f"- Actions applied: {summary['actions_applied']}")
    click.echo(f"- Rows touched: {summary['rows_touched']}")


@cli.command("extract-mfl-history")
@click.option("--start-year", type=int, required=True, help="First season year to extract.")
@click.option("--end-year", type=int, required=True, help="Last season year to extract.")
@click.option(
    "--report-types",
    type=str,
    default="league,players,draftResults,rosters,standings,schedule,transactions",
    show_default=True,
    help="Comma-separated MFL TYPE values.",
)
@click.option(
    "--output-root",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
    default="exports/history",
    show_default=True,
    help="Output folder for CSV and raw JSON exports.",
)
@click.option("--timeout-seconds", type=int, default=20, show_default=True, help="HTTP timeout per request.")
@click.option(
    "--session-cookie",
    type=str,
    default=None,
    help="Optional MFL auth cookie string for private league exports.",
)
@click.option(
    "--max-retries-per-request",
    type=int,
    default=6,
    show_default=True,
    help="Retry count per request for 429/5xx/network errors.",
)
@click.option(
    "--min-interval-seconds",
    type=float,
    default=0.35,
    show_default=True,
    help="Minimum delay between requests to avoid burst throttling.",
)
@click.option(
    "--base-backoff-seconds",
    type=float,
    default=3.0,
    show_default=True,
    help="Base exponential backoff delay for retries.",
)
@click.option(
    "--max-backoff-seconds",
    type=float,
    default=90.0,
    show_default=True,
    help="Upper bound for computed retry delay.",
)
@click.option(
    "--jitter-seconds",
    type=float,
    default=1.0,
    show_default=True,
    help="Random jitter added to retry delay.",
)
@click.option(
    "--cooldown-after-burst-seconds",
    type=float,
    default=15.0,
    show_default=True,
    help="Extra cooldown applied after repeated 429 responses.",
)
@click.option(
    "--burst-threshold",
    type=int,
    default=3,
    show_default=True,
    help="Consecutive 429 count that triggers burst cooldown.",
)
@click.option(
    "--max-retry-after-seconds",
    type=float,
    default=300.0,
    show_default=True,
    help="Cap for server-provided Retry-After delay.",
)
def extract_mfl_history(
    start_year: int,
    end_year: int,
    report_types: str,
    output_root: str,
    timeout_seconds: int,
    session_cookie: str | None,
    max_retries_per_request: int,
    min_interval_seconds: float,
    base_backoff_seconds: float,
    max_backoff_seconds: float,
    jitter_seconds: float,
    cooldown_after_burst_seconds: float,
    burst_threshold: int,
    max_retry_after_seconds: float,
):
    """Extract MFL exports into normalized CSV files for migration."""
    report_type_list = [part.strip() for part in report_types.split(",") if part.strip()]
    summary = run_mfl_history_extract(
        start_year=start_year,
        end_year=end_year,
        report_types=report_type_list,
        output_root=output_root,
        timeout_seconds=timeout_seconds,
        session_cookie=session_cookie,
        max_retries_per_request=max_retries_per_request,
        min_interval_seconds=min_interval_seconds,
        base_backoff_seconds=base_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
        jitter_seconds=jitter_seconds,
        cooldown_after_burst_seconds=cooldown_after_burst_seconds,
        burst_threshold=burst_threshold,
        max_retry_after_seconds=max_retry_after_seconds,
    )

    click.echo("MFL extraction summary")
    click.echo(f"- Seasons requested: {summary['requested_seasons'][0]}..{summary['requested_seasons'][-1]}")
    click.echo(f"- Reports extracted: {summary['extracted_reports']}")
    click.echo(f"- Seasons skipped (missing league id): {summary['skipped_missing_league_id']}")
    click.echo(f"- Failed report pulls: {summary['failed_reports']}")
    click.echo(f"- Retry attempts: {summary['retry_attempts']}")
    click.echo(f"- Throttled retries: {summary['throttled_retries']}")
    click.echo(f"- Unresolved failures: {summary['unresolved_failures']}")
    click.echo(f"- Output root: {summary['output_root']}")


@cli.command("extract-mfl-html-reports")
@click.option("--start-year", type=int, required=True, help="First season year to extract.")
@click.option("--end-year", type=int, required=True, help="Last season year to extract.")
@click.option(
    "--report-keys",
    type=str,
    default="league_champions,league_awards,top_performers_player_stats,starter_points_by_position,points_allowed_by_position,draft_results_detailed",
    show_default=True,
    help="Comma-separated HTML report keys.",
)
@click.option(
    "--output-root",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
    default="exports/history_html",
    show_default=True,
    help="Output folder for CSV and raw HTML report extracts.",
)
@click.option("--timeout-seconds", type=int, default=20, show_default=True, help="HTTP timeout per request.")
@click.option(
    "--session-cookie",
    type=str,
    default=None,
    help="Optional MFL auth cookie string for private league reports.",
)
def extract_mfl_html_reports(
    start_year: int,
    end_year: int,
    report_keys: str,
    output_root: str,
    timeout_seconds: int,
    session_cookie: str | None,
):
    """Extract selected legacy MFL HTML report pages into CSV files."""
    selected_keys = [part.strip() for part in report_keys.split(",") if part.strip()]
    summary = run_extract_mfl_html_reports(
        start_year=start_year,
        end_year=end_year,
        report_keys=selected_keys,
        output_root=output_root,
        timeout_seconds=timeout_seconds,
        session_cookie=session_cookie,
    )

    click.echo("MFL HTML report extraction summary")
    click.echo(f"- Seasons requested: {summary['requested_seasons'][0]}..{summary['requested_seasons'][-1]}")
    click.echo(f"- Reports extracted: {summary['extracted_reports']}")
    click.echo(f"- Seasons skipped (missing host): {summary['skipped_missing_host']}")
    click.echo(f"- Seasons skipped (missing league id): {summary['skipped_missing_league_id']}")
    click.echo(f"- Failed report pulls: {summary['failed_reports']}")
    click.echo(f"- Output root: {summary['output_root']}")


@cli.command("normalize-mfl-html-records")
@click.option(
    "--input-root",
    type=click.Path(file_okay=False, dir_okay=True, exists=True),
    required=True,
    help="Root containing extracted HTML report CSVs.",
)
@click.option(
    "--output-root",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Destination root for normalized CSV outputs (defaults to <input-root>_normalized).",
)
@click.option("--start-year", type=int, default=None, help="Optional minimum season year filter.")
@click.option("--end-year", type=int, default=None, help="Optional maximum season year filter.")
@click.option(
    "--report-keys",
    type=str,
    default="league_champions,league_awards,franchise_records,player_records,matchup_records,all_time_series_records,season_records,career_records,record_streaks",
    show_default=True,
    help="Comma-separated HTML report keys to normalize.",
)
def normalize_mfl_html_records(
    input_root: str,
    output_root: str | None,
    start_year: int | None,
    end_year: int | None,
    report_keys: str,
):
    """Normalize extracted MFL HTML record-family CSVs into stable schemas."""
    if start_year is not None and end_year is not None and end_year < start_year:
        raise click.UsageError("--end-year must be greater than or equal to --start-year")

    selected_keys = [part.strip() for part in report_keys.split(",") if part.strip()]
    summary = run_normalize_mfl_html_records(
        input_root=input_root,
        output_root=output_root,
        start_year=start_year,
        end_year=end_year,
        report_keys=selected_keys,
    )

    click.echo("MFL HTML normalization summary")
    click.echo(f"- Input root: {summary['input_root']}")
    click.echo(f"- Output root: {summary['output_root']}")
    click.echo(f"- Files processed: {summary['files_processed']}")
    click.echo(f"- Files skipped: {summary['files_skipped']}")
    for dataset, rows in summary["rows_written_by_dataset"].items():
        click.echo(f"- {dataset}: {rows} rows")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("load-mfl-html-normalized")
@click.option(
    "--input-roots",
    type=str,
    required=True,
    help="Comma-separated normalized roots (for example 2002_2003 + 2004_2026 outputs).",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    default=False,
    help="Write rows to Postgres (default is dry-run).",
)
@click.option(
    "--truncate-before-load",
    is_flag=True,
    default=False,
    help="Delete existing mfl_html_record_facts rows before loading (apply mode only).",
)
@click.option(
    "--target-league-id",
    type=int,
    default=None,
    help="App league_id to associate with imported HTML fact rows.",
)
def load_mfl_html_normalized(
    input_roots: str,
    apply_changes: bool,
    truncate_before_load: bool,
    target_league_id: int | None,
):
    """Load normalized MFL HTML record datasets into Postgres."""
    roots = [part.strip() for part in input_roots.split(",") if part.strip()]
    if not roots:
        raise click.UsageError("--input-roots must contain at least one path")

    if truncate_before_load and not apply_changes:
        raise click.UsageError("--truncate-before-load requires --apply")

    summary = run_load_mfl_html_normalized(
        input_roots=roots,
        dry_run=not apply_changes,
        truncate_before_load=truncate_before_load,
        target_league_id=target_league_id,
    )

    click.echo("MFL HTML normalized load summary")
    click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
    click.echo(f"- Run id: {summary['run_id']}")
    click.echo(f"- Input roots: {', '.join(summary['input_roots'])}")
    click.echo(f"- Target league id: {summary['target_league_id']}")
    click.echo(f"- Files seen: {summary['files_seen']}")
    click.echo(f"- Files loaded: {summary['files_loaded']}")
    click.echo(f"- Rows seen: {summary['rows_seen']}")
    click.echo(f"- Rows inserted: {summary['rows_inserted']}")
    click.echo(f"- Rows skipped (existing): {summary['rows_skipped_existing']}")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("archive-mfl-html-exports")
@click.option(
    "--input-root",
    type=click.Path(file_okay=False, dir_okay=True, exists=True),
    required=True,
    help="Export root containing raw HTML artifacts to archive.",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    default=False,
    help="Create the archive and manifest on disk (default is dry-run).",
)
@click.option(
    "--prune-html",
    is_flag=True,
    default=False,
    help="Delete the original HTML files after they have been archived (apply mode only).",
)
@click.option(
    "--overwrite-existing",
    is_flag=True,
    default=False,
    help="Replace an existing archive/manifest for the same export root.",
)
def archive_mfl_html_exports(
    input_root: str,
    apply_changes: bool,
    prune_html: bool,
    overwrite_existing: bool,
):
    """Archive recursive HTML artifacts from an MFL export root."""
    if prune_html and not apply_changes:
        raise click.UsageError("--prune-html requires --apply")

    summary = run_archive_mfl_html_exports(
        input_root=input_root,
        dry_run=not apply_changes,
        prune_html=prune_html,
        overwrite_existing=overwrite_existing,
    )

    click.echo("MFL HTML archive summary")
    click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
    click.echo(f"- Run id: {summary['run_id']}")
    click.echo(f"- Input root: {summary['input_root']}")
    click.echo(f"- Archive path: {summary['archive_path']}")
    click.echo(f"- Manifest path: {summary['manifest_path']}")
    click.echo(f"- HTML files seen: {summary['html_files_seen']}")
    click.echo(f"- HTML files archived: {summary['html_files_archived']}")
    click.echo(f"- HTML files pruned: {summary['html_files_pruned']}")
    click.echo(f"- Bytes seen: {summary['bytes_seen']}")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("archive-mfl-json-exports")
@click.option(
    "--input-root",
    type=click.Path(file_okay=False, dir_okay=True, exists=True),
    required=True,
    help="Export root containing JSON artifacts to archive.",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    default=False,
    help="Create the archive and manifest on disk (default is dry-run).",
)
@click.option(
    "--prune-json",
    is_flag=True,
    default=False,
    help="Delete the original JSON files after they have been archived (apply mode only).",
)
@click.option(
    "--overwrite-existing",
    is_flag=True,
    default=False,
    help="Replace an existing archive/manifest for the same export root.",
)
def archive_mfl_json_exports(
    input_root: str,
    apply_changes: bool,
    prune_json: bool,
    overwrite_existing: bool,
):
    """Archive recursive JSON artifacts from an MFL export root."""
    if prune_json and not apply_changes:
        raise click.UsageError("--prune-json requires --apply")

    summary = run_archive_mfl_json_exports(
        input_root=input_root,
        dry_run=not apply_changes,
        prune_json=prune_json,
        overwrite_existing=overwrite_existing,
    )

    click.echo("MFL JSON archive summary")
    click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
    click.echo(f"- Run id: {summary['run_id']}")
    click.echo(f"- Input root: {summary['input_root']}")
    click.echo(f"- Archive path: {summary['archive_path']}")
    click.echo(f"- Manifest path: {summary['manifest_path']}")
    click.echo(f"- JSON files seen: {summary['json_files_seen']}")
    click.echo(f"- JSON files archived: {summary['json_files_archived']}")
    click.echo(f"- JSON files pruned: {summary['json_files_pruned']}")
    click.echo(f"- Bytes seen: {summary['bytes_seen']}")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("archive-mfl-csv-exports")
@click.option(
    "--input-root",
    type=click.Path(file_okay=False, dir_okay=True, exists=True),
    required=True,
    help="Export root containing CSV artifacts to archive.",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    default=False,
    help="Create the archive and manifest on disk (default is dry-run).",
)
@click.option(
    "--prune-csv",
    is_flag=True,
    default=False,
    help="Delete the original CSV files after they have been archived (apply mode only).",
)
@click.option(
    "--overwrite-existing",
    is_flag=True,
    default=False,
    help="Replace an existing archive/manifest for the same export root.",
)
def archive_mfl_csv_exports(
    input_root: str,
    apply_changes: bool,
    prune_csv: bool,
    overwrite_existing: bool,
):
    """Archive recursive CSV artifacts from an MFL export root."""
    if prune_csv and not apply_changes:
        raise click.UsageError("--prune-csv requires --apply")

    summary = run_archive_mfl_csv_exports(
        input_root=input_root,
        dry_run=not apply_changes,
        prune_csv=prune_csv,
        overwrite_existing=overwrite_existing,
    )

    click.echo("MFL CSV archive summary")
    click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
    click.echo(f"- Run id: {summary['run_id']}")
    click.echo(f"- Input root: {summary['input_root']}")
    click.echo(f"- Archive path: {summary['archive_path']}")
    click.echo(f"- Manifest path: {summary['manifest_path']}")
    click.echo(f"- CSV files seen: {summary['csv_files_seen']}")
    click.echo(f"- CSV files archived: {summary['csv_files_archived']}")
    click.echo(f"- CSV files pruned: {summary['csv_files_pruned']}")
    click.echo(f"- Bytes seen: {summary['bytes_seen']}")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("restore-mfl-archive")
@click.option(
    "--archive-path",
    type=click.Path(dir_okay=False, exists=True),
    required=True,
    help="Path to the archived zip file to restore.",
)
@click.option(
    "--destination-root",
    type=click.Path(file_okay=False, dir_okay=True),
    required=True,
    help="Destination folder to restore files into.",
)
@click.option(
    "--manifest-path",
    type=click.Path(dir_okay=False, exists=True),
    default=None,
    help="Optional archive manifest used for file list and checksum verification.",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    default=False,
    help="Extract files to destination (default is dry-run).",
)
@click.option(
    "--overwrite-existing",
    is_flag=True,
    default=False,
    help="Replace an existing non-empty destination folder.",
)
@click.option(
    "--skip-verify-manifest",
    is_flag=True,
    default=False,
    help="Skip manifest file-list and checksum verification.",
)
def restore_mfl_archive(
    archive_path: str,
    destination_root: str,
    manifest_path: str | None,
    apply_changes: bool,
    overwrite_existing: bool,
    skip_verify_manifest: bool,
):
    """Restore a previously archived MFL export zip into a working folder."""
    summary = run_restore_mfl_archive(
        archive_path=archive_path,
        destination_root=destination_root,
        manifest_path=manifest_path,
        dry_run=not apply_changes,
        overwrite_existing=overwrite_existing,
        verify_manifest=not skip_verify_manifest,
    )

    click.echo("MFL archive restore summary")
    click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
    click.echo(f"- Run id: {summary['run_id']}")
    click.echo(f"- Archive path: {summary['archive_path']}")
    click.echo(f"- Destination root: {summary['destination_root']}")
    click.echo(f"- Manifest path: {summary['manifest_path']}")
    click.echo(f"- Verify manifest: {summary['verify_manifest']}")
    click.echo(f"- Files listed: {summary['files_listed']}")
    click.echo(f"- Files restored: {summary['files_restored']}")
    click.echo(f"- Bytes restored: {summary['bytes_restored']}")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("import-mfl-csv")
@click.option("--source-mode", type=click.Choice(["db", "csv"]), default="db", show_default=True, help="Import source mode. Use db (recommended) to read from mfl_html_record_facts.")
@click.option("--input-root", type=click.Path(file_okay=False, dir_okay=True, exists=True), default=None, help="Legacy CSV mode: extraction root folder (required when --source-mode=csv).")
@click.option("--source-league-id", type=str, default=None, help="Optional MFL league_id filter when --source-mode=db.")
@click.option("--target-league-id", type=int, required=True, help="App league_id receiving imported rows.")
@click.option("--start-year", type=int, required=True, help="First season year to import.")
@click.option("--end-year", type=int, required=True, help="Last season year to import.")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Write changes (default dry-run).")
def import_mfl_csv(
    source_mode: str,
    input_root: str | None,
    source_league_id: str | None,
    target_league_id: int,
    start_year: int,
    end_year: int,
    apply_changes: bool,
):
    """Import normalized MFL CSV files into app tables with validation."""
    if source_mode == "csv" and not input_root:
        raise click.UsageError("--input-root is required when --source-mode=csv")

    summary = run_import_mfl_csv(
        input_root=input_root,
        target_league_id=target_league_id,
        start_year=start_year,
        end_year=end_year,
        dry_run=not apply_changes,
        source_mode=source_mode,
        source_league_id=source_league_id,
    )

    click.echo("MFL import summary")
    click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
    click.echo(f"- Source mode: {source_mode}")
    if source_mode == "csv":
        click.echo(f"- Input root: {input_root}")
    elif source_league_id:
        click.echo(f"- Source league id: {source_league_id}")
    click.echo(f"- Files checked: {summary['files_checked']}")
    click.echo(f"- Files missing: {summary['files_missing']}")
    click.echo(f"- Rows validated: {summary['rows_validated']}")
    click.echo(f"- Rows invalid: {summary['rows_invalid']}")
    click.echo(f"- Players inserted: {summary['players_inserted']}")
    click.echo(f"- Players matched: {summary['players_matched']}")
    click.echo(f"- Draft picks inserted: {summary['draft_picks_inserted']}")
    click.echo(f"- Draft picks skipped: {summary['draft_picks_skipped']}")
    click.echo(f"- Matchups inserted: {summary['matchups_inserted']}")
    click.echo(f"- Matchups skipped: {summary['matchups_skipped']}")
    click.echo(f"- BYE matchups skipped: {summary['bye_matchups_skipped']}")
    click.echo(f"- Skipped missing owner map: {summary['skipped_missing_owner_map']}")
    click.echo(f"- Skipped missing player map: {summary['skipped_missing_player_map']}")


@cli.command("bootstrap-mfl-franchise-users")
@click.option("--franchises-csv", type=click.Path(file_okay=True, dir_okay=False, exists=True), default=None, help="Legacy mode: path to a staged franchises CSV (e.g. exports/history_staged_2003/franchises/2003.csv).")
@click.option("--source-season", type=int, default=None, help="DB mode: season year to pull franchises from mfl_html_record_facts.")
@click.option("--source-league-id", type=str, default=None, help="Optional MFL league_id filter when using --source-season.")
@click.option("--target-league-id", type=int, required=True, help="App league_id to create stub users in.")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Write users to DB (default dry-run).")
def bootstrap_mfl_franchise_users(
    franchises_csv: str | None,
    source_season: int | None,
    source_league_id: str | None,
    target_league_id: int,
    apply_changes: bool,
):
    """Create locked stub user accounts for historical MFL franchises not yet in the league."""
    if franchises_csv and source_season is not None:
        raise click.UsageError("Choose one input source: either --franchises-csv (legacy) or --source-season (DB mode), not both.")
    if not franchises_csv and source_season is None:
        raise click.UsageError("Provide an input source: --source-season for DB mode (recommended) or --franchises-csv for legacy CSV mode.")

    db = SessionLocal()
    try:
        rows: list[dict] = []
        source_label = ""
        if franchises_csv:
            with open(franchises_csv, newline="", encoding="utf-8") as fh:
                rows = list(_csv.DictReader(fh))
            source_label = f"csv:{franchises_csv}"
        else:
            facts_query = (
                db.query(models.MflHtmlRecordFact)
                .filter(models.MflHtmlRecordFact.season == source_season)
                .filter(models.MflHtmlRecordFact.dataset_key == "html_franchises_normalized")
            )
            if source_league_id:
                facts_query = facts_query.filter(models.MflHtmlRecordFact.league_id == source_league_id)

            facts = facts_query.all()
            for fact in facts:
                record = fact.record_json or {}
                if not isinstance(record, dict):
                    continue
                franchise_id = str(record.get("franchise_id") or "").strip()
                franchise_name = str(record.get("franchise_name") or "").strip()
                if not franchise_id or not franchise_name:
                    continue
                row_season = record.get("season") if record.get("season") is not None else source_season
                row_league_id = str(record.get("league_id") or fact.league_id or "").strip()
                if source_league_id and row_league_id and row_league_id != source_league_id:
                    continue
                rows.append(
                    {
                        "season": str(row_season or "").strip(),
                        "franchise_id": franchise_id,
                        "franchise_name": franchise_name,
                        "owner_name": str(record.get("owner_name") or "").strip(),
                        "league_id": row_league_id,
                    }
                )

            source_label = f"db:season={source_season}" + (f",league_id={source_league_id}" if source_league_id else "")

        if not rows:
            raise click.ClickException("No franchise rows found for the selected source. Verify season/league filters or provide a valid CSV.")

        existing_in_league = db.query(models.User).filter(models.User.league_id == target_league_id).all()
        existing_team_lower = {(u.team_name or "").strip().lower() for u in existing_in_league}
        all_usernames_lower = {(u.username or "").strip().lower() for u in db.query(models.User.username).all()}
        existing_stub_by_franchise_id = {
            username.rsplit("_", 1)[-1]: user.id
            for user in existing_in_league
            if (username := (user.username or "").strip().lower()).startswith("hist_") and "_" in username
        }

        to_create: list[dict] = []
        skipped: list[str] = []
        seen_names: set[str] = set()
        updates: list[dict] = []

        for row in rows:
            franchise_name = (row.get("franchise_name") or "").strip()
            franchise_id = (row.get("franchise_id") or "").strip()
            season = (row.get("season") or "").strip()
            if not franchise_id:
                continue
            if not franchise_name:
                continue
            fname_lower = franchise_name.lower()
            existing_stub_id = existing_stub_by_franchise_id.get(franchise_id)
            if existing_stub_id is not None:
                updates.append({
                    "user_id": existing_stub_id,
                    "team_name": franchise_name,
                    "franchise_id": franchise_id,
                    "season": season,
                })
                skipped.append(franchise_name)
                continue
            if fname_lower in existing_team_lower or fname_lower in seen_names:
                skipped.append(franchise_name)
                continue
            seen_names.add(fname_lower)

            base = f"hist_{season}_{franchise_id}".lower()
            username = base
            suffix = 2
            while username in all_usernames_lower:
                username = f"{base}_{suffix}"
                suffix += 1
            all_usernames_lower.add(username)

            to_create.append({
                "username": username,
                "team_name": franchise_name,
                "franchise_id": franchise_id,
                "season": season,
            })

        click.echo("Bootstrap MFL franchise users")
        click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
        click.echo(f"- Source: {source_label}")
        click.echo(f"- Target league: {target_league_id}")
        click.echo(f"- Rows loaded: {len(rows)}")
        click.echo(f"- Users to create: {len(to_create)}")
        click.echo(f"- Existing stubs to refresh: {len(updates)}")
        click.echo(f"- Already exist (skipped): {len(skipped)}")
        for entry in to_create:
            click.echo(f"  [{entry['season']}:{entry['franchise_id']}] {entry['team_name']} -> username={entry['username']}")
        for entry in updates:
            click.echo(f"  [{entry['season']}:{entry['franchise_id']}] refresh existing stub -> team_name={entry['team_name']}")

        if apply_changes:
            for entry in updates:
                user = db.query(models.User).filter(models.User.id == entry["user_id"]).one_or_none()
                if user is not None:
                    user.team_name = entry["team_name"]

            for entry in to_create:
                user = models.User(
                    username=entry["username"],
                    email=None,
                    hashed_password=get_password_hash(f"locked_{entry['franchise_id']}_{target_league_id}"),
                    league_id=target_league_id,
                    team_name=entry["team_name"],
                    is_superuser=False,
                    is_commissioner=False,
                )
                db.add(user)
            if updates or to_create:
                db.commit()
            if to_create:
                click.echo(f"- Inserted {len(to_create)} stub users into league {target_league_id}.")
            if updates:
                click.echo(f"- Refreshed {len(updates)} existing stub users in league {target_league_id}.")
    finally:
        db.close()


@cli.command("scaffold-mfl-manual-csv")
@click.option("--start-year", type=int, required=True, help="First season year to scaffold.")
@click.option("--end-year", type=int, required=True, help="Last season year to scaffold.")
@click.option(
    "--output-root",
    type=click.Path(file_okay=False, dir_okay=True),
    default="exports/history_manual",
    show_default=True,
    help="Output folder for manual header-only CSV templates.",
)
@click.option(
    "--report-types",
    type=str,
    default="franchises,players,draftResults",
    show_default=True,
    help="Comma-separated report names to scaffold.",
)
def scaffold_mfl_manual_csv(
    start_year: int,
    end_year: int,
    output_root: str,
    report_types: str,
):
    """Create header-only CSV templates for manual legacy-season ingestion."""
    if end_year < start_year:
        raise click.UsageError("--end-year must be greater than or equal to --start-year")

    report_type_list = [part.strip() for part in report_types.split(",") if part.strip()]
    summary = run_scaffold_mfl_manual_csv(
        start_year=start_year,
        end_year=end_year,
        output_root=output_root,
        report_types=report_type_list,
    )

    click.echo("Manual CSV scaffold summary")
    click.echo(f"- Seasons scaffolded: {summary['seasons'][0]}..{summary['seasons'][-1]}")
    click.echo(f"- Report types: {','.join(summary['report_types'])}")
    click.echo(f"- Files created: {summary['files_created']}")
    click.echo(f"- Output root: {summary['output_root']}")


@cli.command("stage-mfl-html-for-import")
@click.option("--start-year", type=int, required=True, help="First season year to stage.")
@click.option("--end-year", type=int, required=True, help="Last season year to stage.")
@click.option(
    "--api-root",
    type=click.Path(file_okay=False, dir_okay=True, exists=True),
    required=True,
    help="Root containing canonical API extraction CSVs.",
)
@click.option(
    "--html-root",
    type=click.Path(file_okay=False, dir_okay=True, exists=True),
    required=True,
    help="Root containing HTML report extraction CSVs.",
)
@click.option(
    "--output-root",
    type=click.Path(file_okay=False, dir_okay=True),
    required=True,
    help="Destination root to stage importer-compatible CSVs plus HTML supplements.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help=(
        "Overwrite destination files when they already exist. "
        "Manual override files (manual_overrides/) are never overwritten "
        "regardless of this flag, to preserve operator edits."
    ),
)
def stage_mfl_html_for_import(
    start_year: int,
    end_year: int,
    api_root: str,
    html_root: str,
    output_root: str,
    overwrite: bool,
):
    """Stage HTML + API extraction outputs into an importer-compatible root.

    LEGACY: This command is part of the CSV staging pipeline and is only needed
    when using the legacy CSV import path (import-mfl-csv --source-mode=csv).
    It is not required for the default DB-backed import workflow.
    Set FFPI_ALLOW_LEGACY_CSV_PIPELINE=1 to enable.
    """
    if _os.environ.get("FFPI_ALLOW_LEGACY_CSV_PIPELINE") != "1":
        raise click.ClickException(
            "stage-mfl-html-for-import is a LEGACY archival tool for the CSV staging pipeline.\n"
            "The active MFL import path (import-mfl-csv --source-mode=db) reads directly from\n"
            "mfl_html_record_facts and does not require CSV staging.\n\n"
            "To run this legacy command, set FFPI_ALLOW_LEGACY_CSV_PIPELINE=1."
        )
    if end_year < start_year:
        raise click.UsageError("--end-year must be greater than or equal to --start-year")

    summary = run_stage_mfl_html_for_import(
        start_year=start_year,
        end_year=end_year,
        api_root=api_root,
        html_root=html_root,
        output_root=output_root,
        overwrite=overwrite,
    )

    click.echo("MFL staging summary")
    click.echo(f"- Seasons: {summary['seasons'][0]}..{summary['seasons'][-1]}")
    click.echo(f"- Required CSVs copied: {summary['copied_required_files']}")
    click.echo(f"- Required CSVs scaffolded: {summary['scaffolded_required_files']}")
    click.echo(f"- HTML report CSVs copied: {summary['copied_html_reports']}")
    click.echo(f"- Draft manual templates created: {summary['draft_results_manual_templates']}")
    click.echo(f"- Draft manual override rows merged: {summary['manual_override_rows_merged']}")
    click.echo(f"- Output root: {summary['output_root']}")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("prepare-mfl-draft-backfill-sheet")
@click.option("--input-root", type=click.Path(file_okay=False, dir_okay=True, exists=True), required=True, help="Staged import root containing draft/manual CSVs.")
@click.option("--start-year", type=int, required=True, help="First season year to prepare.")
@click.option("--end-year", type=int, required=True, help="Last season year to prepare.")
@click.option(
    "--output-root",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Optional destination for fill-ready backfill sheets (default: <input-root>/manual_overrides/draft_backfill_sheets).",
)
@click.option(
    "--include-filled",
    is_flag=True,
    default=False,
    help="Include rows that already have player_mfl_id values.",
)
def prepare_mfl_draft_backfill_sheet(
    input_root: str,
    start_year: int,
    end_year: int,
    output_root: str | None,
    include_filled: bool,
):
    """Generate fill-ready draft backfill sheets with snake/auction guidance.

    LEGACY: Requires a CSV staging root from the legacy CSV import pipeline.
    Set FFPI_ALLOW_LEGACY_CSV_PIPELINE=1 to enable.
    """
    if _os.environ.get("FFPI_ALLOW_LEGACY_CSV_PIPELINE") != "1":
        raise click.ClickException(
            "prepare-mfl-draft-backfill-sheet is a LEGACY archival tool that reads from\n"
            "staged CSV extraction files. It is not part of the active DB-backed import workflow.\n\n"
            "To run this legacy command, set FFPI_ALLOW_LEGACY_CSV_PIPELINE=1."
        )
    if end_year < start_year:
        raise click.UsageError("--end-year must be greater than or equal to --start-year")

    summary = run_prepare_mfl_draft_backfill_sheet(
        input_root=input_root,
        start_year=start_year,
        end_year=end_year,
        output_root=output_root,
        include_filled=include_filled,
    )

    click.echo("MFL draft backfill sheet summary")
    click.echo(f"- Seasons: {summary['seasons'][0]}..{summary['seasons'][-1]}")
    click.echo(f"- Sheets written: {summary['sheets_written']}")
    click.echo(f"- Rows written: {summary['rows_written']}")
    click.echo(f"- Rows skipped already filled: {summary['rows_skipped_already_filled']}")
    click.echo(f"- Style counts: {summary['style_counts']}")
    click.echo(f"- Output root: {summary['output_root']}")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("apply-mfl-draft-backfill-sheet")
@click.option("--input-root", type=click.Path(file_okay=False, dir_okay=True, exists=True), required=True, help="Staged import root containing manual override CSVs.")
@click.option("--start-year", type=int, required=True, help="First season year to apply.")
@click.option("--end-year", type=int, required=True, help="Last season year to apply.")
@click.option(
    "--sheet-root",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Optional folder containing completed backfill sheets (default: <input-root>/manual_overrides/draft_backfill_sheets).",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    default=False,
    help="Write updates into manual override CSVs (default: report-only dry-run).",
)
@click.option(
    "--require-source-url",
    is_flag=True,
    default=False,
    help="Only apply rows that include manual_source_url evidence.",
)
@click.option(
    "--enforce-2002-source-policy/--no-enforce-2002-source-policy",
    default=True,
    help="Enforce policy that blocks known invalid 2002 draft sources and requires source URL evidence.",
)
def apply_mfl_draft_backfill_sheet(
    input_root: str,
    start_year: int,
    end_year: int,
    sheet_root: str | None,
    apply_changes: bool,
    require_source_url: bool,
    enforce_2002_source_policy: bool,
):
    """Apply completed draft backfill sheets into manual override CSVs.

    LEGACY: Reads from and writes to staged CSV extraction files.
    Set FFPI_ALLOW_LEGACY_CSV_PIPELINE=1 to enable.
    """
    if _os.environ.get("FFPI_ALLOW_LEGACY_CSV_PIPELINE") != "1":
        raise click.ClickException(
            "apply-mfl-draft-backfill-sheet is a LEGACY archival tool that reads/writes\n"
            "staged CSV extraction files. It is not part of the active DB-backed import workflow.\n\n"
            "To run this legacy command, set FFPI_ALLOW_LEGACY_CSV_PIPELINE=1."
        )
    if end_year < start_year:
        raise click.UsageError("--end-year must be greater than or equal to --start-year")

    summary = run_apply_mfl_draft_backfill_sheet(
        input_root=input_root,
        start_year=start_year,
        end_year=end_year,
        sheet_root=sheet_root,
        apply_changes=apply_changes,
        require_source_url=require_source_url,
        enforce_2002_source_policy=enforce_2002_source_policy,
    )

    click.echo("MFL backfill sheet apply summary")
    click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
    click.echo(f"- Seasons: {summary['seasons'][0]}..{summary['seasons'][-1]}")
    click.echo(f"- Sheets missing: {summary['sheets_missing']}")
    click.echo(f"- Candidate rows: {summary['candidate_rows']}")
    click.echo(f"- Rows updated: {summary['rows_updated']}")
    click.echo(f"- Rows appended: {summary['rows_appended']}")
    click.echo(f"- Rows skipped missing player id: {summary['rows_skipped_missing_player_id']}")
    click.echo(f"- Rows skipped missing source url: {summary['rows_skipped_missing_source_url']}")
    click.echo(f"- Rows skipped blocked source policy: {summary['rows_skipped_blocked_source_policy']}")
    click.echo(f"- Sheet root: {summary['sheet_root']}")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("resolve-mfl-draft-backfill-names")
@click.option("--input-root", type=click.Path(file_okay=False, dir_okay=True, exists=True), required=True, help="Staged import root containing player snapshots and backfill sheets.")
@click.option("--start-year", type=int, required=True, help="First season year to resolve.")
@click.option("--end-year", type=int, required=True, help="Last season year to resolve.")
@click.option(
    "--sheet-root",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Optional sheet folder (default: <input-root>/manual_overrides/draft_backfill_sheets).",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    default=False,
    help="Write resolved player_mfl_id values back into sheet CSVs (default: report-only dry-run).",
)
def resolve_mfl_draft_backfill_names(
    input_root: str,
    start_year: int,
    end_year: int,
    sheet_root: str | None,
    apply_changes: bool,
):
    """Resolve manual draft player names to season player_mfl_id values.

    LEGACY: Reads from staged CSV backfill sheets.
    Set FFPI_ALLOW_LEGACY_CSV_PIPELINE=1 to enable.
    """
    if _os.environ.get("FFPI_ALLOW_LEGACY_CSV_PIPELINE") != "1":
        raise click.ClickException(
            "resolve-mfl-draft-backfill-names is a LEGACY archival tool that reads\n"
            "staged CSV backfill sheets. It is not part of the active DB-backed import workflow.\n\n"
            "To run this legacy command, set FFPI_ALLOW_LEGACY_CSV_PIPELINE=1."
        )
    if end_year < start_year:
        raise click.UsageError("--end-year must be greater than or equal to --start-year")

    summary = run_resolve_mfl_draft_backfill_names(
        input_root=input_root,
        start_year=start_year,
        end_year=end_year,
        sheet_root=sheet_root,
        apply_changes=apply_changes,
    )

    click.echo("MFL draft backfill name resolve summary")
    click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
    click.echo(f"- Seasons: {summary['seasons'][0]}..{summary['seasons'][-1]}")
    click.echo(f"- Rows seen: {summary['rows_seen']}")
    click.echo(f"- Rows matched: {summary['rows_matched']}")
    click.echo(f"- Rows already filled: {summary['rows_already_filled']}")
    click.echo(f"- Rows skipped no manual name: {summary['rows_skipped_no_manual_name']}")
    click.echo(f"- Rows unmatched: {summary['rows_unmatched']}")
    click.echo(f"- Rows ambiguous: {summary['rows_ambiguous']}")
    click.echo(f"- Sheet root: {summary['sheet_root']}")
    if summary["warnings"]:
        click.echo(f"- Warnings: {len(summary['warnings'])}")


@cli.command("reconcile-mfl-import")
@click.option(
    "--source-mode",
    type=click.Choice(["db", "csv"]),
    default="db",
    show_default=True,
    help=(
        "Reconciliation source mode. 'db' (default, recommended) reads source counts from "
        "mfl_html_record_facts. 'csv' is LEGACY and requires --input-root and "
        "FFPI_ALLOW_LEGACY_CSV_PIPELINE=1."
    ),
)
@click.option(
    "--input-root",
    type=click.Path(file_okay=False, dir_okay=True, exists=True),
    default=None,
    help="LEGACY CSV mode only: path to staged CSV extraction root (required when --source-mode=csv).",
)
@click.option("--target-league-id", type=int, required=True, help="App league_id to reconcile against imported rows.")
@click.option("--start-year", type=int, required=True, help="First season year to reconcile.")
@click.option("--end-year", type=int, required=True, help="Last season year to reconcile.")
@click.option("--output-json", type=click.Path(file_okay=True, dir_okay=False), default=None, help="Optional JSON output path for machine-readable mismatch report.")
def reconcile_mfl_import(
    source_mode: str,
    input_root: str | None,
    target_league_id: int,
    start_year: int,
    end_year: int,
    output_json: str | None,
):
    """Compare MFL source counts against imported DB counts by season.

    DB mode (default) reads from mfl_html_record_facts; no CSV files required.
    CSV mode is LEGACY and reads from staged extraction files under --input-root.
    """
    if end_year < start_year:
        raise click.UsageError("--end-year must be greater than or equal to --start-year")

    if source_mode == "csv" and not input_root:
        raise click.UsageError("--input-root is required when --source-mode=csv")

    try:
        summary = run_reconcile_mfl_import(
            input_root=input_root,
            target_league_id=target_league_id,
            start_year=start_year,
            end_year=end_year,
            source_mode=source_mode,
            output_json=output_json,
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("MFL import reconciliation summary")
    click.echo(f"- Source mode: {source_mode}")
    click.echo(f"- Seasons: {summary['seasons'][0]}..{summary['seasons'][-1]}")
    click.echo(f"- Mismatch count: {summary['mismatch_count']}")

    if output_json:
        click.echo(f"- JSON report: {output_json}")


@cli.command("finalize-week")
@click.option("--league-id", type=int, required=True, help="Target league ID.")
@click.option("--week", type=int, required=True, help="Week number to finalize.")
@click.option(
    "--season",
    type=int,
    default=lambda: datetime.now(timezone.utc).year,
    show_default="current UTC year",
    help="Stat season used for points lookup.",
)
@click.option("--season-year", type=int, default=None, help="Optional scoring season year.")
def finalize_week_command(league_id: int, week: int, season: int, season_year: int | None):
    """Finalize one league week and lock lineup edits for that week.

    This command is designed to run via scheduler (for example Tuesday 4 AM cron).
    """
    result = run_finalization(
        league_id=league_id,
        week=week,
        season=season,
        season_year=season_year,
    )

    click.echo(
        f"Finalized league={result['league_id']} week={result['week']} "
        f"matchups={result['matchups_finalized']}"
    )


# ====== VALIDATION COMMAND GROUP ======
@cli.group("validate")
def validate_group():
    """Validation and audit commands for MFL import completeness."""
    pass


@validate_group.command("mfl-import")
@click.option("--league-id", type=int, required=True, help="League ID to validate.")
@click.option("--json-output", type=click.Path(dir_okay=False), default=None, help="Optional JSON output file.")
def validate_mfl_import_cmd(league_id: int, json_output: str | None):
    """Validate MFL matched counts, FK integrity, and duplicate detection."""
    summary = run_validate_mfl_import(league_id=league_id, json_output=json_output)
    output = format_validation_output(summary)
    click.echo(output)
    
    if summary["errors"]:
        raise click.ClickException("Validation failed with errors")


@validate_group.command("season-hierarchy")
@click.option("--league-id", type=int, required=True, help="League ID to validate.")
def validate_season_hierarchy_cmd(league_id: int):
    """Validate season hierarchy completeness (all seasons mapped)."""
    summary = run_validate_season_hierarchy(league_id=league_id)
    output = format_season_hierarchy_output(summary)
    click.echo(output)
    
    if summary["errors"]:
        raise click.ClickException("Validation failed with errors")


@validate_group.command("league-readiness")
@click.option("--league-id", type=int, required=True, help="League ID to validate.")
def validate_league_readiness_cmd(league_id: int):
    """Validate league readiness for 2026 season operations."""
    summary = run_validate_league_readiness(league_id=league_id)
    output = format_league_readiness_output(summary)
    click.echo(output)
    
    if summary["errors"]:
        raise click.ClickException("Validation failed with errors")


if __name__ == "__main__":
    cli()
