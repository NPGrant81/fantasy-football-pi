"""create manager_efficiency table

Revision ID: 0009_manager_efficiency
Revises: 0008_add_taxi_flag
Create Date: 2026-02-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0009_manager_efficiency'
down_revision = '0008_add_taxi_flag'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'manager_efficiency',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('league_id', sa.Integer(), nullable=False, index=True),
        sa.Column('manager_id', sa.Integer(), nullable=False, index=True),
        sa.Column('season', sa.Integer(), nullable=False, index=True),
        sa.Column('week', sa.Integer(), nullable=False, index=True),
        sa.Column('actual_points_total', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('optimal_points_total', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('points_left_on_bench', sa.Numeric(10, 2), nullable=True),
        sa.Column('efficiency_rating', sa.Numeric(5, 4), nullable=True),
        sa.Column('worst_sit_player_name', sa.String(), nullable=True),
        sa.Column('worst_sit_points_diff', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('league_id', 'manager_id', 'season', 'week', name='uq_mgr_eff_league_mgr_season_week')
    )


def downgrade():
    op.drop_table('manager_efficiency')
