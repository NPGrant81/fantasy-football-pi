"""add league history team-owner mapping table

Revision ID: 20260328_01
Revises: 20260311_01
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_01"
down_revision = "20260311_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "league_history_team_owner_map",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("team_name", sa.String(length=160), nullable=False),
        sa.Column("team_name_key", sa.String(length=160), nullable=False),
        sa.Column("owner_name", sa.String(length=160), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "season", "team_name_key", name="uq_league_history_team_owner_map_key"),
    )
    op.create_index(
        "ix_league_history_team_owner_map_league",
        "league_history_team_owner_map",
        ["league_id"],
    )
    op.create_index(
        "ix_league_history_team_owner_map_season",
        "league_history_team_owner_map",
        ["season"],
    )
    op.create_index(
        "ix_league_history_team_owner_map_team_key",
        "league_history_team_owner_map",
        ["team_name_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_league_history_team_owner_map_team_key", table_name="league_history_team_owner_map")
    op.drop_index("ix_league_history_team_owner_map_season", table_name="league_history_team_owner_map")
    op.drop_index("ix_league_history_team_owner_map_league", table_name="league_history_team_owner_map")
    op.drop_table("league_history_team_owner_map")
