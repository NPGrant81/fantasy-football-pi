"""add owner_season_behaviors table for draft spend behavioral features

Revision ID: 0023
Revises: 0022_add_position_and_snapshot_tables
Create Date: 2026-05-02

Note: depends on migration 0022 which is in PR #450. Apply after that PR merges.
"""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022_add_position_and_snapshot_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "owner_season_behaviors" not in inspector.get_table_names():
        op.create_table(
            "owner_season_behaviors",
            sa.Column("id", sa.Integer(), primary_key=True, index=True, nullable=False),
            sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id"), nullable=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("season_year", sa.Integer(), nullable=False),
            sa.Column("starting_budget", sa.Numeric(10, 2), nullable=True),
            sa.Column("total_spend", sa.Numeric(10, 2), nullable=True),
            sa.Column("remaining_budget", sa.Numeric(10, 2), nullable=True),
            sa.Column("budget_source", sa.String(32), nullable=True),
            sa.Column("overspent", sa.Boolean(), nullable=True),
            sa.Column("spend_by_position", sa.JSON(), nullable=True),
            sa.Column("pick_count_by_position", sa.JSON(), nullable=True),
            sa.Column("position_spend_pct", sa.JSON(), nullable=True),
            sa.Column("max_bid_by_position", sa.JSON(), nullable=True),
            sa.Column("avg_bid_by_position", sa.JSON(), nullable=True),
            sa.Column("aggressiveness_index", sa.Float(), nullable=True),
            sa.Column("positional_bias_index", sa.Float(), nullable=True),
            sa.Column("etl_version", sa.String(32), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
        )

        op.create_unique_constraint(
            "uq_osb_league_owner_season",
            "owner_season_behaviors",
            ["league_id", "owner_id", "season_year"],
        )
        op.create_index(
            "ix_osb_league_season",
            "owner_season_behaviors",
            ["league_id", "season_year"],
        )
        op.create_index(
            "ix_owner_season_behaviors_season_year",
            "owner_season_behaviors",
            ["season_year"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "owner_season_behaviors" in inspector.get_table_names():
        op.drop_table("owner_season_behaviors")
