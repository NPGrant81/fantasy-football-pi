"""add optimal_lineup_json and indexes, create leaderboard view

Revision ID: 0010_efficiency_details
Revises: 0009_manager_efficiency
Create Date: 2026-02-26 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0010_efficiency_details'
down_revision = '0009_manager_efficiency'
branch_labels = None
depends_on = None


def upgrade():
    # add JSON column for storing the optimal lineup
    op.add_column('manager_efficiency', sa.Column('optimal_lineup_json', sa.JSON(), nullable=True))

    # create indexes to speed up frequent queries
    op.create_index('idx_league_season', 'manager_efficiency', ['league_id', 'season'])
    op.create_index('idx_manager_weekly', 'manager_efficiency', ['manager_id', 'week'])

    # create a leaderboard view
    op.execute(
        """
        CREATE OR REPLACE VIEW league_efficiency_leaderboard AS
        SELECT 
            manager_id,
            league_id,
            COUNT(week) as weeks_played,
            SUM(actual_points_total) as total_actual,
            SUM(optimal_points_total) as total_optimal,
            ROUND(AVG(actual_points_total / NULLIF(optimal_points_total, 0)), 4) as avg_efficiency,
            SUM(points_left_on_bench) as total_points_lost
        FROM manager_efficiency
        GROUP BY manager_id, league_id
        ORDER BY avg_efficiency DESC;
        """
    )


def downgrade():
    op.execute("DROP VIEW IF EXISTS league_efficiency_leaderboard;")
    op.drop_index('idx_manager_weekly', table_name='manager_efficiency')
    op.drop_index('idx_league_season', table_name='manager_efficiency')
    op.drop_column('manager_efficiency', 'optimal_lineup_json')
