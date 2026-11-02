"""Extend the frozen bootstrap contract to the historical ingestion head."""

import importlib

revision = "bootstrap_0030"
down_revision = "bootstrap_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    importlib.import_module("db.migrations.0030_historical_ingestion").upgrade()


def downgrade() -> None:
    raise RuntimeError(
        "Historical schema adoption is forward-only; restore a verified backup."
    )
