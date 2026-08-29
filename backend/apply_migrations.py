"""Apply all Alembic migration heads before starting the application."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.db_config import load_backend_env_file, resolve_database_url


ALEMBIC_CONFIG_PATH = Path(__file__).resolve().with_name("alembic.ini")
BOOTSTRAP_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "db" / "bootstrap"
BOOTSTRAP_MAIN_REVISION = "0028_reconcile_runtime_schema"
CORE_APPLICATION_TABLES = frozenset({"leagues", "players", "users"})


def _database_is_empty(database_engine) -> bool:
    table_names = set(inspect(database_engine).get_table_names())
    if not table_names.isdisjoint(CORE_APPLICATION_TABLES):
        return False
    if "alembic_version" not in table_names:
        return True

    with database_engine.connect() as connection:
        existing_revisions = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalars().all()
    if existing_revisions:
        raise RuntimeError(
            "Refusing FFPI bootstrap: database has Alembic history but no FFPI core tables"
        )
    return True


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
        if _database_is_empty(migration_engine):
            command.upgrade(_bootstrap_config(config_path), "head")
            command.stamp(config, BOOTSTRAP_MAIN_REVISION, purge=True)
        command.upgrade(config, "heads")
    finally:
        migration_engine.dispose()


if __name__ == "__main__":
    apply_migrations()
