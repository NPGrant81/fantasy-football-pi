"""Extend the bootstrap to the separate historical observation contract."""

import importlib

revision = "bootstrap_0031"
down_revision = "bootstrap_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    importlib.import_module("db.migrations.0031_historical_observations").upgrade()


def downgrade() -> None:
    raise RuntimeError(
        "Historical observations are forward-only; restore a verified backup."
    )
