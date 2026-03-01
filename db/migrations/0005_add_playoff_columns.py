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
    op.add_column('league_settings', sa.Column('playoff_qualifiers', sa.Integer, server_default='6', nullable=False))
    op.add_column('league_settings', sa.Column('playoff_reseed', sa.Boolean, server_default='false', nullable=False))
    op.add_column('league_settings', sa.Column('playoff_consolation', sa.Boolean, server_default='true', nullable=False))
    op.add_column('league_settings', sa.Column('playoff_tiebreakers', sa.JSON, server_default='["points_for","head_to_head","division_wins","wins"]', nullable=False))


def downgrade():
    op.drop_column('league_settings', 'playoff_tiebreakers')
    op.drop_column('league_settings', 'playoff_consolation')
    op.drop_column('league_settings', 'playoff_reseed')
    op.drop_column('league_settings', 'playoff_qualifiers')
