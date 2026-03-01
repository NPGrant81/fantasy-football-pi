"""
add playoff settings columns to league_settings
"""
revision = '0005_add_playoff_columns'
down_revision = '0004_add_division_to_users'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column['name'] for column in inspector.get_columns('league_settings')}

    if 'playoff_qualifiers' not in existing:
        op.add_column('league_settings', sa.Column('playoff_qualifiers', sa.Integer, server_default='6', nullable=False))
    if 'playoff_reseed' not in existing:
        op.add_column('league_settings', sa.Column('playoff_reseed', sa.Boolean, server_default='false', nullable=False))
    if 'playoff_consolation' not in existing:
        op.add_column('league_settings', sa.Column('playoff_consolation', sa.Boolean, server_default='true', nullable=False))
    if 'playoff_tiebreakers' not in existing:
        op.add_column('league_settings', sa.Column('playoff_tiebreakers', sa.JSON, server_default='["points_for","head_to_head","division_wins","wins"]', nullable=False))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column['name'] for column in inspector.get_columns('league_settings')}

    if 'playoff_tiebreakers' in existing:
        op.drop_column('league_settings', 'playoff_tiebreakers')
    if 'playoff_consolation' in existing:
        op.drop_column('league_settings', 'playoff_consolation')
    if 'playoff_reseed' in existing:
        op.drop_column('league_settings', 'playoff_reseed')
    if 'playoff_qualifiers' in existing:
        op.drop_column('league_settings', 'playoff_qualifiers')
