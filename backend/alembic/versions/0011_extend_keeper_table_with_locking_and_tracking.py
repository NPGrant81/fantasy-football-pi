"""
add years_kept_count, locked_at, and approval flag to keepers table
"""
revision = '0011_extend_keeper_table_with_locking_and_tracking'
down_revision = '0006_add_keeper_and_transaction_tables'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('keepers', sa.Column('years_kept_count', sa.Integer, nullable=False, server_default='1'))
    op.add_column('keepers', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('keepers', sa.Column('approved_by_commish', sa.Boolean, nullable=False, server_default='false'))
    # ensure combination of owner, season, player remains unique
    op.create_unique_constraint('ux_keeper_owner_season_player', 'keepers', ['owner_id', 'season', 'player_id'])


def downgrade():
    op.drop_constraint('ux_keeper_owner_season_player', 'keepers', type_='unique')
    op.drop_column('keepers', 'approved_by_commish')
    op.drop_column('keepers', 'locked_at')
    op.drop_column('keepers', 'years_kept_count')
