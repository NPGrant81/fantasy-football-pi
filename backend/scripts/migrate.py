"""Backward-compatible wrapper for the deployment migration runner.

Usage:
    python backend/scripts/migrate.py

Prefer `python -m backend.apply_migrations` for new automation.
"""
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.apply_migrations import apply_migrations  # noqa: E402


def upgrade_head():
    apply_migrations()


if __name__ == "__main__":
    print("Applying alembic migrations...")
    upgrade_head()
    print("Migrations complete.")
