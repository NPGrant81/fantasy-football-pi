"""add trade governance fields to league_settings

Revision ID: 20260427_01
Revises: 20260401_01
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_01"
down_revision = "20260401_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("league_settings", sa.Column("trade_veto_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("league_settings", sa.Column("trade_veto_threshold", sa.Integer(), nullable=True))
    op.add_column("league_settings", sa.Column("trade_review_period_hours", sa.Integer(), nullable=True))
    op.add_column("league_settings", sa.Column("trade_max_players_per_side", sa.Integer(), nullable=True))
    op.add_column("league_settings", sa.Column("trade_league_vote_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("league_settings", sa.Column("trade_league_vote_threshold", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("league_settings", "trade_league_vote_threshold")
    op.drop_column("league_settings", "trade_league_vote_enabled")
    op.drop_column("league_settings", "trade_max_players_per_side")
    op.drop_column("league_settings", "trade_review_period_hours")
    op.drop_column("league_settings", "trade_veto_threshold")
    op.drop_column("league_settings", "trade_veto_enabled")
