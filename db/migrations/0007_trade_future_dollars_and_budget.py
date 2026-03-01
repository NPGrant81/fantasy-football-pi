"""
add future draft dollar columns for trades and budgets
"""
revision = '0007_trade_future_dollars_and_budget'
down_revision = '0006_add_keeper_and_transaction_tables'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # add columns to trade_proposals
    trade_columns = {column['name'] for column in inspector.get_columns('trade_proposals')}
    if 'offered_dollars' not in trade_columns:
        op.add_column('trade_proposals', sa.Column('offered_dollars', sa.Numeric, nullable=False, server_default='0'))
    if 'requested_dollars' not in trade_columns:
        op.add_column('trade_proposals', sa.Column('requested_dollars', sa.Numeric, nullable=False, server_default='0'))

    # add cap to league_settings
    league_columns = {column['name'] for column in inspector.get_columns('league_settings')}
    if 'future_draft_cap' not in league_columns:
        op.add_column('league_settings', sa.Column('future_draft_cap', sa.Integer, nullable=False, server_default='0'))

    # add budget to users
    user_columns = {column['name'] for column in inspector.get_columns('users')}
    if 'future_draft_budget' not in user_columns:
        op.add_column('users', sa.Column('future_draft_budget', sa.Integer, nullable=False, server_default='0'))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_columns = {column['name'] for column in inspector.get_columns('users')}
    if 'future_draft_budget' in user_columns:
        op.drop_column('users', 'future_draft_budget')

    league_columns = {column['name'] for column in inspector.get_columns('league_settings')}
    if 'future_draft_cap' in league_columns:
        op.drop_column('league_settings', 'future_draft_cap')

    trade_columns = {column['name'] for column in inspector.get_columns('trade_proposals')}
    if 'requested_dollars' in trade_columns:
        op.drop_column('trade_proposals', 'requested_dollars')
    if 'offered_dollars' in trade_columns:
        op.drop_column('trade_proposals', 'offered_dollars')
