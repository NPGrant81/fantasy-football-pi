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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('manager_efficiency')}

    # add JSON column for storing the optimal lineup
    if 'optimal_lineup_json' not in columns:
        op.add_column('manager_efficiency', sa.Column('optimal_lineup_json', sa.JSON(), nullable=True))

    # create indexes to speed up frequent queries
    indexes = {index['name'] for index in inspector.get_indexes('manager_efficiency')}
    if 'idx_league_season' not in indexes:
        op.create_index('idx_league_season', 'manager_efficiency', ['league_id', 'season'])
    if 'idx_manager_weekly' not in indexes:
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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index['name'] for index in inspector.get_indexes('manager_efficiency')}
    if 'idx_manager_weekly' in indexes:
        op.drop_index('idx_manager_weekly', table_name='manager_efficiency')
    if 'idx_league_season' in indexes:
        op.drop_index('idx_league_season', table_name='manager_efficiency')
    columns = {column['name'] for column in inspector.get_columns('manager_efficiency')}
    if 'optimal_lineup_json' in columns:
        op.drop_column('manager_efficiency', 'optimal_lineup_json')
