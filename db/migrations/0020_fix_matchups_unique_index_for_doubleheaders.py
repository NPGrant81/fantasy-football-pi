"""fix matchups unique index for same-week doubleheaders

Revision ID: 0020_fix_matchups_unique_index_for_doubleheaders
Revises: 0019_add_season_hierarchy
Create Date: 2026-03-18
"""

from alembic import op


revision = "0020_fix_matchups_unique_index_for_doubleheaders"
down_revision = "0019_add_season_hierarchy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uix_matchups_league_season_week_home")
    op.execute(
        """
        CREATE UNIQUE INDEX uix_matchups_league_season_week_home_away
        ON matchups (league_id, season, week, home_team_id, away_team_id)
        WHERE season IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uix_matchups_league_season_week_home_away")
    op.execute(
        """
        CREATE UNIQUE INDEX uix_matchups_league_season_week_home
        ON matchups (league_id, season, week, home_team_id)
        WHERE season IS NOT NULL
        """
    )
