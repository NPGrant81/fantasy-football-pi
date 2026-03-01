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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('keepers')}

    if 'years_kept_count' not in columns:
        op.add_column('keepers', sa.Column('years_kept_count', sa.Integer, nullable=False, server_default='1'))
    if 'locked_at' not in columns:
        op.add_column('keepers', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))
    if 'approved_by_commish' not in columns:
        op.add_column('keepers', sa.Column('approved_by_commish', sa.Boolean, nullable=False, server_default='false'))

    # ensure combination of owner, season, player remains unique
    unique_constraints = inspector.get_unique_constraints('keepers')
    has_unique = any(
        uc.get('name') == 'ux_keeper_owner_season_player'
        or uc.get('column_names') == ['owner_id', 'season', 'player_id']
        for uc in unique_constraints
    )
    if not has_unique:
        op.create_unique_constraint('ux_keeper_owner_season_player', 'keepers', ['owner_id', 'season', 'player_id'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    unique_constraints = inspector.get_unique_constraints('keepers')
    if any(uc.get('name') == 'ux_keeper_owner_season_player' for uc in unique_constraints):
        op.drop_constraint('ux_keeper_owner_season_player', 'keepers', type_='unique')

    columns = {column['name'] for column in inspector.get_columns('keepers')}
    if 'approved_by_commish' in columns:
        op.drop_column('keepers', 'approved_by_commish')
    if 'locked_at' in columns:
        op.drop_column('keepers', 'locked_at')
    if 'years_kept_count' in columns:
        op.drop_column('keepers', 'years_kept_count')
