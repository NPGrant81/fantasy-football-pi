"""Apply all Alembic migration heads before starting the application."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from backend.db_config import load_backend_env_file, resolve_database_url


ALEMBIC_CONFIG_PATH = Path(__file__).resolve().with_name("alembic.ini")
BOOTSTRAP_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "db" / "bootstrap"
BOOTSTRAP_MAIN_REVISION = "0028_reconcile_runtime_schema"


def _database_is_empty(database_engine) -> bool:
    table_names = set(inspect(database_engine).get_table_names())
    return not table_names or table_names == {"alembic_version"}


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
