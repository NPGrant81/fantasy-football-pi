"""
add complex scoring_rules schema with range, calc_type, positions
"""
revision = '0003_complex_scoring_rules'
down_revision = '0002_add_source_to_manual_player_mappings'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    # create enums if not exist (postgres-compatible across versions)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'scoring_category') THEN
                CREATE TYPE scoring_category AS ENUM ('passing','rushing','receiving','defense','kicking','special_teams');
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'calc_type') THEN
                CREATE TYPE calc_type AS ENUM ('per_unit','flat_bonus');
            END IF;
        END
        $$;
        """
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('scoring_rules'):
        op.create_table(
            'scoring_rules',
            sa.Column('rule_id', sa.Integer, primary_key=True),
            sa.Column('league_id', sa.Integer, sa.ForeignKey('leagues.id', ondelete='CASCADE'), nullable=False),
            sa.Column('category', postgresql.ENUM('passing','rushing','receiving','defense','kicking','special_teams', name='scoring_category', create_type=False), nullable=False),
            sa.Column('event_name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('range_min', sa.Numeric(10,2), nullable=False, server_default='0'),
            sa.Column('range_max', sa.Numeric(10,2), nullable=False, server_default='9999.99'),
            sa.Column('point_value', sa.Numeric(10,2), nullable=False),
            sa.Column('calculation_type', postgresql.ENUM('per_unit','flat_bonus', name='calc_type', create_type=False), nullable=False, server_default='flat_bonus'),
            sa.Column('applicable_positions', sa.JSON, nullable=False, server_default='["ALL"]'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        )

    existing_indexes = {index['name'] for index in inspector.get_indexes('scoring_rules')}
    if 'idx_league_scoring' not in existing_indexes:
        op.create_index('idx_league_scoring', 'scoring_rules', ['league_id', 'category'])
    if 'idx_scoring_positions' not in existing_indexes:
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scoring_positions
            ON scoring_rules
            USING gin ((applicable_positions::jsonb));
            """
        )


def downgrade():
    op.drop_index('idx_scoring_positions', table_name='scoring_rules')
    op.drop_index('idx_league_scoring', table_name='scoring_rules')
    op.drop_table('scoring_rules')
    op.execute('DROP TYPE IF EXISTS calc_type')
    op.execute('DROP TYPE IF EXISTS scoring_category')