"""add trades and trade_assets tables

Revision ID: 20260330_01
Revises: 20260328_01
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260330_01"
down_revision = "20260328_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_a_id", sa.Integer(), nullable=False),
        sa.Column("team_b_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("commissioner_comments", sa.String(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["team_a_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["team_b_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trades_id"), "trades", ["id"], unique=False)
    op.create_index(op.f("ix_trades_league_id"), "trades", ["league_id"], unique=False)
    op.create_index(op.f("ix_trades_team_a_id"), "trades", ["team_a_id"], unique=False)
    op.create_index(op.f("ix_trades_team_b_id"), "trades", ["team_b_id"], unique=False)
    op.create_index(op.f("ix_trades_created_by_user_id"), "trades", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_trades_status"), "trades", ["status"], unique=False)
    op.create_index("ix_trades_league_status", "trades", ["league_id", "status"], unique=False)
    op.create_index("ix_trades_submitted_at", "trades", ["submitted_at"], unique=False)
    op.create_index("ix_trades_teams", "trades", ["team_a_id", "team_b_id"], unique=False)

    op.create_table(
        "trade_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_id", sa.Integer(), nullable=False),
        sa.Column("asset_side", sa.String(length=1), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("draft_pick_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("season_year", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["trade_id"], ["trades.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["draft_pick_id"], ["draft_picks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trade_assets_id"), "trade_assets", ["id"], unique=False)
    op.create_index(op.f("ix_trade_assets_trade_id"), "trade_assets", ["trade_id"], unique=False)
    op.create_index("ix_trade_assets_trade_side", "trade_assets", ["trade_id", "asset_side"], unique=False)
    op.create_index("ix_trade_assets_type", "trade_assets", ["asset_type"], unique=False)
    op.create_index("ix_trade_assets_player", "trade_assets", ["player_id"], unique=False)
    op.create_index("ix_trade_assets_draft_pick", "trade_assets", ["draft_pick_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trade_assets_draft_pick", table_name="trade_assets")
    op.drop_index("ix_trade_assets_player", table_name="trade_assets")
    op.drop_index("ix_trade_assets_type", table_name="trade_assets")
    op.drop_index("ix_trade_assets_trade_side", table_name="trade_assets")
    op.drop_index(op.f("ix_trade_assets_trade_id"), table_name="trade_assets")
    op.drop_index(op.f("ix_trade_assets_id"), table_name="trade_assets")
    op.drop_table("trade_assets")

    op.drop_index("ix_trades_teams", table_name="trades")
    op.drop_index("ix_trades_submitted_at", table_name="trades")
    op.drop_index("ix_trades_league_status", table_name="trades")
    op.drop_index(op.f("ix_trades_status"), table_name="trades")
    op.drop_index(op.f("ix_trades_created_by_user_id"), table_name="trades")
    op.drop_index(op.f("ix_trades_team_b_id"), table_name="trades")
    op.drop_index(op.f("ix_trades_team_a_id"), table_name="trades")
    op.drop_index(op.f("ix_trades_league_id"), table_name="trades")
    op.drop_index(op.f("ix_trades_id"), table_name="trades")
    op.drop_table("trades")
