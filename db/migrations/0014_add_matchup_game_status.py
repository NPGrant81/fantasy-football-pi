"""
add game_status to matchups for tracking game progression
"""
revision = '0014_add_matchup_game_status'
down_revision = '0013_add_team_visual_assets'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # add game_status to matchups
    matchup_columns = {column['name'] for column in inspector.get_columns('matchups')}
    
    if 'game_status' not in matchup_columns:
        # Default to 'NOT_STARTED' for existing matchups
        op.add_column('matchups', sa.Column('game_status', sa.String, nullable=False, server_default='NOT_STARTED'))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    matchup_columns = {column['name'] for column in inspector.get_columns('matchups')}
    
    if 'game_status' in matchup_columns:
        op.drop_column('matchups', 'game_status')
