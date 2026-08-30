"""Apply all Alembic migration heads before starting the application."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from backend.db_config import load_backend_env_file, resolve_database_url


ALEMBIC_CONFIG_PATH = Path(__file__).resolve().with_name("alembic.ini")
BOOTSTRAP_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "db" / "bootstrap"
BOOTSTRAP_MAIN_REVISION = "0028_reconcile_runtime_schema"
FFPI_APPLICATION_TABLES = frozenset(
    {
        "admin_audit_logs",
        "bug_reports",
        "canonical_player_snapshots",
        "division_config_snapshots",
        "division_name_reports",
        "divisions",
        "draft_budgets",
        "draft_picks",
        "draft_values",
        "economic_ledger",
        "keeper_rules",
        "keepers",
        "league_history_team_owner_map",
        "league_mfl_seasons",
        "league_settings",
        "leagues",
        "lineup_submissions",
        "live_scoring_ingest_events",
        "manager_efficiency",
        "manual_player_mappings",
        "matchups",
        "mfl_html_record_facts",
        "mfl_ingestion_files",
        "mfl_ingestion_runs",
        "nfl_games",
        "owner_season_behaviors",
        "password_reset_tokens",
        "platform_projections",
        "player_aliases",
        "player_id_mappings",
        "player_news_items",
        "player_news_links",
        "player_news_sentiment_trends",
        "player_seasons",
        "player_weekly_stats",
        "players",
        "playoff_matches",
        "playoff_snapshots",
        "positions",
        "refresh_tokens",
        "revoked_tokens",
        "scoring_rule_change_logs",
        "scoring_rule_proposals",
        "scoring_rule_votes",
        "scoring_rules",
        "scoring_template_rules",
        "scoring_templates",
        "site_visits",
        "trade_assets",
        "trade_events",
        "trade_proposals",
        "trades",
        "transaction_history",
        "unmatched_players",
        "users",
        "validated_draft_results",
        "waiver_budgets",
        "waiver_claims",
    }
)


def _database_is_empty(
    database_engine,
    known_revisions: frozenset[str],
    head_revisions: frozenset[str] = frozenset(),
) -> bool:
    table_names = set(inspect(database_engine).get_table_names())
    ffpi_tables = table_names & FFPI_APPLICATION_TABLES
    existing_revisions: set[str] = set()

    if "alembic_version" in table_names:
        with database_engine.connect() as connection:
            existing_revisions = set(
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalars().all()
            )

    unknown_revisions = existing_revisions - known_revisions
    if unknown_revisions:
        revisions = ", ".join(sorted(unknown_revisions))
        raise RuntimeError(
            "Refusing FFPI migration: database has unknown Alembic revision(s): "
            f"{revisions}. Restore the expected FFPI migration history or use a "
            "separate database before retrying."
        )
    if existing_revisions:
        if not ffpi_tables:
            raise RuntimeError(
                "Refusing FFPI migration: database has FFPI Alembic history but no "
                "recognized FFPI tables. Restore the schema from backup before retrying."
            )
        if head_revisions.issubset(existing_revisions) and head_revisions:
            missing_tables = FFPI_APPLICATION_TABLES - ffpi_tables
            if missing_tables:
                tables = ", ".join(sorted(missing_tables))
                raise RuntimeError(
                    "Refusing FFPI migration: database claims the current Alembic "
                    "head but has an incomplete FFPI schema. Missing table(s): "
                    f"{tables}. Restore the schema from backup before retrying."
                )
        return False
    if ffpi_tables:
        tables = ", ".join(sorted(ffpi_tables))
        raise RuntimeError(
            "Refusing FFPI bootstrap: database contains a partial FFPI schema without "
            f"Alembic history. Detected table(s): {tables}. Restore the schema or "
            "remove the FFPI objects before retrying."
        )
    return True


def _known_revisions(config: Config) -> frozenset[str]:
    script = ScriptDirectory.from_config(config)
    return frozenset(revision.revision for revision in script.walk_revisions())


def _head_revisions(config: Config) -> frozenset[str]:
    return frozenset(ScriptDirectory.from_config(config).get_heads())


def _bootstrap_config(config_path: Path) -> Config:
    config = Config(str(config_path))
    config.set_main_option("script_location", str(BOOTSTRAP_SCRIPT_PATH))
    config.set_main_option(
        "version_locations",
        str(BOOTSTRAP_SCRIPT_PATH / "versions"),
    )
    return config


def apply_migrations(config_path: Path = ALEMBIC_CONFIG_PATH) -> None:
    load_backend_env_file()
    database_url = resolve_database_url(
        require_explicit=True,
        context="deployment migrations",
    )
    migration_engine = create_engine(database_url, pool_pre_ping=True)
    try:
        config = Config(str(config_path))
        if _database_is_empty(
            migration_engine,
            _known_revisions(config),
            _head_revisions(config),
        ):
            command.upgrade(_bootstrap_config(config_path), "head")
            command.stamp(config, BOOTSTRAP_MAIN_REVISION, purge=True)
        command.upgrade(config, "heads")
    finally:
        migration_engine.dispose()


if __name__ == "__main__":
    apply_migrations()
