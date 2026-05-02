"""0024 – add validated_draft_results table

This migration stores cleaned, validated historical draft picks produced by
the ETL validation pipeline (Issue #105 / #363).  The table is independent
of the #103 / #104 migration chain and may be applied directly on top of
0021.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# Alembic revision identifiers
revision = "0024_add_validated_draft_results_table"
down_revision = "0021_add_league_settings_trade_governance_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    if "validated_draft_results" in existing_tables:
        return

    op.create_table(
        "validated_draft_results",
        sa.Column("id", sa.Integer, primary_key=True, index=True, autoincrement=True),
        sa.Column("league_id", sa.Integer, sa.ForeignKey("leagues.id"), nullable=False),
        sa.Column("season_year", sa.Integer, nullable=False),
        sa.Column("owner_id", sa.Integer, nullable=False),
        sa.Column("player_id", sa.Integer, nullable=False),
        sa.Column("position_id", sa.Integer, nullable=True),
        sa.Column("team_id", sa.Integer, nullable=True),
        sa.Column("winning_bid", sa.Float, nullable=True),
        sa.Column("is_keeper", sa.Boolean, nullable=False, server_default="false"),
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
        "uq_validated_draft_results_pick",
        "validated_draft_results",
        ["league_id", "season_year", "owner_id", "player_id"],
    )
    op.create_index(
        "ix_validated_draft_results_league_season",
        "validated_draft_results",
        ["league_id", "season_year"],
    )
    op.create_index(
        "ix_validated_draft_results_player",
        "validated_draft_results",
        ["player_id"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "validated_draft_results" not in inspector.get_table_names():
        return

    op.drop_index("ix_validated_draft_results_player", table_name="validated_draft_results")
    op.drop_index("ix_validated_draft_results_league_season", table_name="validated_draft_results")
    op.drop_constraint("uq_validated_draft_results_pick", "validated_draft_results", type_="unique")
    op.drop_table("validated_draft_results")
