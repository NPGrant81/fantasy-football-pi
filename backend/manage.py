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
