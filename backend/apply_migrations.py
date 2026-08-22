"""Apply all Alembic migration heads before starting the application."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from backend.database import engine


ALEMBIC_CONFIG_PATH = Path(__file__).resolve().with_name("alembic.ini")
BOOTSTRAP_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "db" / "bootstrap"
BOOTSTRAP_MAIN_REVISION = "0028_reconcile_runtime_schema"


def _database_is_empty() -> bool:
    table_names = set(inspect(engine).get_table_names())
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
    config = Config(str(config_path))
    if _database_is_empty():
        command.upgrade(_bootstrap_config(config_path), "head")
        command.stamp(config, BOOTSTRAP_MAIN_REVISION, purge=True)
    command.upgrade(config, "heads")


if __name__ == "__main__":
    apply_migrations()
