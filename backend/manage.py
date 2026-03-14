"""Utility script for ad-hoc backend tasks.

Run `python -m backend.manage seed` to populate the database with the
default admin user + sample league.  This replaces the previous startup
handler, eliminating the need for every test to trigger the seeder.
"""

import click
from datetime import datetime, timezone

from .database import SessionLocal, engine, Base
from .scripts.seed import run_seeder
from .scripts.audit_player_duplicates import run_audit as run_player_duplicate_audit
from .scripts.audit_invalid_players import run_invalid_player_audit
from .scripts.extract_mfl_history import run_mfl_history_extract
from .scripts.import_mfl_csv import run_import_mfl_csv
from .scripts.reconcile_mfl_import import run_reconcile_mfl_import
from .scripts.scaffold_mfl_manual_csv import run_scaffold_mfl_manual_csv
from .scripts.finalize_week import run_finalization
from .core.security import get_password_hash


@click.group()
def cli():
    pass


@cli.command()
def seed():
    """Execute the auto-seeder using the session factory.

    Before seeding we must ensure the schema exists – the original
    startup handler created the tables for us, but running the seeder as a
    standalone command means the database can be completely empty.
    """
    # create tables if missing (works with any SQLAlchemy dialect)
    print("Creating database tables…")
    Base.metadata.create_all(bind=engine)

    print("Running seeder…")
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
def extract_mfl_history(
    start_year: int,
    end_year: int,
    report_types: str,
    output_root: str,
    timeout_seconds: int,
    session_cookie: str | None,
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
    )

    click.echo("MFL extraction summary")
    click.echo(f"- Seasons requested: {summary['requested_seasons'][0]}..{summary['requested_seasons'][-1]}")
    click.echo(f"- Reports extracted: {summary['extracted_reports']}")
    click.echo(f"- Seasons skipped (missing league id): {summary['skipped_missing_league_id']}")
    click.echo(f"- Failed report pulls: {summary['failed_reports']}")
    click.echo(f"- Output root: {summary['output_root']}")


@cli.command("import-mfl-csv")
@click.option("--input-root", type=click.Path(file_okay=False, dir_okay=True, exists=True), default="exports/history", show_default=True, help="CSV extraction root folder.")
@click.option("--target-league-id", type=int, required=True, help="App league_id receiving imported rows.")
@click.option("--start-year", type=int, required=True, help="First season year to import.")
@click.option("--end-year", type=int, required=True, help="Last season year to import.")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Write changes (default dry-run).")
def import_mfl_csv(
    input_root: str,
    target_league_id: int,
    start_year: int,
    end_year: int,
    apply_changes: bool,
):
    """Import normalized MFL CSV files into app tables with validation."""
    summary = run_import_mfl_csv(
        input_root=input_root,
        target_league_id=target_league_id,
        start_year=start_year,
        end_year=end_year,
        dry_run=not apply_changes,
    )

    click.echo("MFL CSV import summary")
    click.echo(f"- Mode: {'apply' if apply_changes else 'dry-run'}")
    click.echo(f"- Files checked: {summary['files_checked']}")
    click.echo(f"- Files missing: {summary['files_missing']}")
    click.echo(f"- Rows validated: {summary['rows_validated']}")
    click.echo(f"- Rows invalid: {summary['rows_invalid']}")
    click.echo(f"- Players inserted: {summary['players_inserted']}")
    click.echo(f"- Players matched: {summary['players_matched']}")
    click.echo(f"- Draft picks inserted: {summary['draft_picks_inserted']}")
    click.echo(f"- Draft picks skipped: {summary['draft_picks_skipped']}")
    click.echo(f"- Skipped missing owner map: {summary['skipped_missing_owner_map']}")
    click.echo(f"- Skipped missing player map: {summary['skipped_missing_player_map']}")


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


@cli.command("reconcile-mfl-import")
@click.option("--input-root", type=click.Path(file_okay=False, dir_okay=True, exists=True), default="exports/history", show_default=True, help="CSV extraction root folder.")
@click.option("--target-league-id", type=int, required=True, help="App league_id to reconcile against imported rows.")
@click.option("--start-year", type=int, required=True, help="First season year to reconcile.")
@click.option("--end-year", type=int, required=True, help="Last season year to reconcile.")
@click.option("--output-json", type=click.Path(file_okay=True, dir_okay=False), default=None, help="Optional JSON output path for machine-readable mismatch report.")
def reconcile_mfl_import(
    input_root: str,
    target_league_id: int,
    start_year: int,
    end_year: int,
    output_json: str | None,
):
    """Compare MFL CSV source counts against imported DB counts by season."""
    if end_year < start_year:
        raise click.UsageError("--end-year must be greater than or equal to --start-year")

    summary = run_reconcile_mfl_import(
        input_root=input_root,
        target_league_id=target_league_id,
        start_year=start_year,
        end_year=end_year,
        output_json=output_json,
    )

    click.echo("MFL import reconciliation summary")
    click.echo(f"- Seasons: {summary['seasons'][0]}..{summary['seasons'][-1]}")
    click.echo(f"- Mismatch count: {summary['mismatch_count']}")
    click.echo(f"- Warnings: {len(summary['warnings'])}")
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


if __name__ == "__main__":
    cli()
