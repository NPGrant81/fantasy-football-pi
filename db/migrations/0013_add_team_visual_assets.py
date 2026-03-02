"""
add team logo and color fields to users table for matchup visualization
"""
revision = '0013_add_team_visual_assets'
down_revision = '0012_add_keeper_max_years'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # add team visual fields to users
    user_columns = {column['name'] for column in inspector.get_columns('users')}
    
    if 'team_logo_url' not in user_columns:
        op.add_column('users', sa.Column('team_logo_url', sa.String, nullable=True))
    
    if 'team_color_primary' not in user_columns:
        op.add_column('users', sa.Column('team_color_primary', sa.String, nullable=True, server_default='#3b82f6'))
    
    if 'team_color_secondary' not in user_columns:
        op.add_column('users', sa.Column('team_color_secondary', sa.String, nullable=True, server_default='#1e40af'))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_columns = {column['name'] for column in inspector.get_columns('users')}
    
    if 'team_color_secondary' in user_columns:
        op.drop_column('users', 'team_color_secondary')
    
    if 'team_color_primary' in user_columns:
        op.drop_column('users', 'team_color_primary')
    
    if 'team_logo_url' in user_columns:
        op.drop_column('users', 'team_logo_url')
