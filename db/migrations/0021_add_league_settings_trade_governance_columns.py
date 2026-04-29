"""add trade governance and missing trade window columns to league_settings

Revision ID: 0021
Revises: 0020_fix_matchups_unique_index_for_doubleheaders
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020_fix_matchups_unique_index_for_doubleheaders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("league_settings")}

    additions = [
        ("trade_start_at", sa.DateTime(timezone=True), {}),
        ("trade_end_at", sa.DateTime(timezone=True), {}),
        ("allow_playoff_trades", sa.Boolean(), {"nullable": False, "server_default": sa.text("true")}),
        ("require_commissioner_approval", sa.Boolean(), {"nullable": False, "server_default": sa.text("true")}),
        ("trade_veto_enabled", sa.Boolean(), {"nullable": False, "server_default": sa.text("false")}),
        ("trade_veto_threshold", sa.Integer(), {}),
        ("trade_review_period_hours", sa.Integer(), {}),
        ("trade_max_players_per_side", sa.Integer(), {}),
        ("trade_league_vote_enabled", sa.Boolean(), {"nullable": False, "server_default": sa.text("false")}),
        ("trade_league_vote_threshold", sa.Integer(), {}),
    ]
    for col_name, col_type, kwargs in additions:
        if col_name not in existing:
            op.add_column("league_settings", sa.Column(col_name, col_type, **kwargs))


def downgrade() -> None:
    op.drop_column("league_settings", "trade_league_vote_threshold")
    op.drop_column("league_settings", "trade_league_vote_enabled")
    op.drop_column("league_settings", "trade_max_players_per_side")
    op.drop_column("league_settings", "trade_review_period_hours")
    op.drop_column("league_settings", "trade_veto_threshold")
    op.drop_column("league_settings", "trade_veto_enabled")
    op.drop_column("league_settings", "require_commissioner_approval")
    op.drop_column("league_settings", "allow_playoff_trades")
    op.drop_column("league_settings", "trade_end_at")
    op.drop_column("league_settings", "trade_start_at")
