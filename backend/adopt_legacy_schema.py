"""Explicit command for adopting the pinned pre-Alembic PostgreSQL schema."""

from __future__ import annotations

import argparse
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from backend import apply_migrations as migration_runner
from backend.db_config import resolve_database_url
from backend.legacy_schema_bridge import (
    LegacyAdoptionReport,
    finalize_legacy_schema_adoption,
    inspect_legacy_database,
    prepare_legacy_schema,
)


INITIAL_REVISION = "0001_create_draft_value_tables"


def _format_report(report: LegacyAdoptionReport) -> str:
    counts = ", ".join(
        f"{table}={count}" for table, count in report.table_row_counts
    )
    return (
        f"Database: {report.database}\n"
        f"State: {report.phase}\n"
        f"Source rows: {counts}\n"
        f"Scoring-rule rows to map: {report.scoring_rule_rows}\n"
        f"Division groups to map: {report.division_groups}\n"
        "Scoring mapping: points -> point_value; description (or category) -> "
        "event_name; range 0..9999.99; flat_bonus; ALL positions.\n"
        "Original source tables will be retained in schema "
        "'ffpi_legacy_archive'."
    )


def _run_adoption(database_url: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        report = prepare_legacy_schema(engine)
        print(_format_report(report))
        if report.phase.startswith("resume:complete:"):
            _verify_canonical_heads(engine)
            return

        has_history = "alembic_version" in migration_runner.inspect(
            engine
        ).get_table_names()
        if not has_history:
            command.upgrade(
                Config(str(migration_runner.ALEMBIC_CONFIG_PATH)),
                INITIAL_REVISION,
            )

        migration_runner.apply_migrations()
        _verify_canonical_heads(engine)
        finalize_legacy_schema_adoption(engine)
        _verify_canonical_heads(engine)
    finally:
        engine.dispose()


def _verify_canonical_heads(engine: Engine) -> None:
    with engine.connect() as connection:
        actual_heads = frozenset(
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars()
        )
    expected_heads = migration_runner._head_revisions(
        Config(str(migration_runner.ALEMBIC_CONFIG_PATH))
    )
    if actual_heads != expected_heads:
        raise RuntimeError(
            "Legacy adoption has not reached all canonical Alembic heads. "
            f"Expected {sorted(expected_heads)}; found {sorted(actual_heads)}. "
            "The archive is retained for recovery."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or explicitly adopt the pinned pre-Alembic schema. "
            "This command is never run automatically at application startup."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the forward-only bridge and canonical migrations.",
    )
    parser.add_argument(
        "--confirm-database",
        help="Required with --apply; must exactly match DATABASE_URL's database.",
    )
    args = parser.parse_args(argv)

    database_url = resolve_database_url(
        require_explicit=True,
        context="legacy schema adoption",
    )
    parsed_url = make_url(database_url)
    if not parsed_url.database:
        parser.error("DATABASE_URL must name a target database.")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        report = inspect_legacy_database(engine)
        print(_format_report(report))
    finally:
        engine.dispose()

    if not args.apply:
        print("Dry run only. No persistent schema or data changes were made.")
        return 0

    if args.confirm_database != parsed_url.database:
        parser.error(
            "--confirm-database must exactly match the database name in DATABASE_URL."
        )

    _run_adoption(database_url)
    print("Legacy adoption completed at all canonical Alembic heads.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
