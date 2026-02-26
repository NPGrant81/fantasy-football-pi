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
    # add columns to trade_proposals
    op.add_column('trade_proposals', sa.Column('offered_dollars', sa.Numeric, nullable=False, server_default='0'))
    op.add_column('trade_proposals', sa.Column('requested_dollars', sa.Numeric, nullable=False, server_default='0'))

    # add cap to league_settings
    op.add_column('league_settings', sa.Column('future_draft_cap', sa.Integer, nullable=False, server_default='0'))

    # add budget to users
    op.add_column('users', sa.Column('future_draft_budget', sa.Integer, nullable=False, server_default='0'))


def downgrade():
    op.drop_column('users', 'future_draft_budget')
    op.drop_column('league_settings', 'future_draft_cap')
    op.drop_column('trade_proposals', 'requested_dollars')
    op.drop_column('trade_proposals', 'offered_dollars')
