"""add trade window settings to league_settings

Revision ID: 20260401_01
Revises: 20260330_02
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260401_01"
down_revision = "20260330_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("league_settings", sa.Column("trade_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("league_settings", sa.Column("trade_end_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("league_settings", sa.Column("allow_playoff_trades", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("league_settings", sa.Column("require_commissioner_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("league_settings", "require_commissioner_approval")
    op.drop_column("league_settings", "allow_playoff_trades")
    op.drop_column("league_settings", "trade_end_at")
    op.drop_column("league_settings", "trade_start_at")
