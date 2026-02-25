"""
add complex scoring_rules schema with range, calc_type, positions
"""
revision = '0003_complex_scoring_rules'
down_revision = '0002_add_source_to_manual_player_mappings'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    # create enums if not exist (postgres) - safe to run repeatedly
    op.execute("CREATE TYPE IF NOT EXISTS scoring_category AS ENUM ('passing','rushing','receiving','defense','kicking','special_teams')")
    op.execute("CREATE TYPE IF NOT EXISTS calc_type AS ENUM ('per_unit','flat_bonus')")

    op.create_table(
        'scoring_rules',
        sa.Column('rule_id', sa.Integer, primary_key=True),
        sa.Column('league_id', sa.Integer, sa.ForeignKey('leagues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.Enum('passing','rushing','receiving','defense','kicking','special_teams', name='scoring_category'), nullable=False),
        sa.Column('event_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('range_min', sa.Numeric(10,2), nullable=False, server_default='0'),
        sa.Column('range_max', sa.Numeric(10,2), nullable=False, server_default='9999.99'),
        sa.Column('point_value', sa.Numeric(10,2), nullable=False),
        sa.Column('calculation_type', sa.Enum('per_unit','flat_bonus', name='calc_type'), nullable=False, server_default='flat_bonus'),
        sa.Column('applicable_positions', sa.JSON, nullable=False, server_default='["ALL"]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_index('idx_league_scoring', 'scoring_rules', ['league_id', 'category'])
    op.create_index('idx_scoring_positions', 'scoring_rules', ['applicable_positions'], postgresql_using='gin')


def downgrade():
    op.drop_index('idx_scoring_positions', table_name='scoring_rules')
    op.drop_index('idx_league_scoring', table_name='scoring_rules')
    op.drop_table('scoring_rules')
    op.execute('DROP TYPE IF EXISTS calc_type')
    op.execute('DROP TYPE IF EXISTS scoring_category')