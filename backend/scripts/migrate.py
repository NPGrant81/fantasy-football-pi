"""Helper script to apply Alembic migrations without using the CLI.

Usage:
    python backend/scripts/migrate.py

This is useful in environments where `python -m alembic` fails due to
module path issues; it invokes the Alembic API directly using the
`alembic.ini` configuration in the backend directory.
"""
import os
from alembic.config import Config
from alembic import command


def upgrade_head():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg_path = os.path.join(base, "alembic.ini")
    cfg = Config(cfg_path)
    # ensure the script location is relative to backend/ as expected
    cfg.set_main_option("script_location", "backend/alembic")
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    print("Applying alembic migrations...")
    upgrade_head()
    print("Migrations complete.")
