"""
add keeper tables and transaction history
"""
revision = '0006_add_keeper_and_transaction_tables'
down_revision = '0005_add_playoff_columns'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # keeper_rules table
    if not inspector.has_table('keeper_rules'):
        op.create_table(
            'keeper_rules',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('league_id', sa.Integer, sa.ForeignKey('leagues.id'), unique=True, nullable=False),
            sa.Column('max_keepers', sa.Integer, nullable=False, server_default='3'),
            sa.Column('cost_type', sa.String, nullable=False, server_default='round'),
            sa.Column('cost_inflation', sa.Integer, nullable=False, server_default='0'),
            sa.Column('deadline_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('waiver_policy', sa.Boolean, nullable=False, server_default='true'),
            sa.Column('trade_deadline', sa.DateTime(timezone=True), nullable=True),
            sa.Column('drafted_only', sa.Boolean, nullable=False, server_default='true'),
        )

    # keepers table
    if not inspector.has_table('keepers'):
        op.create_table(
            'keepers',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('league_id', sa.Integer, sa.ForeignKey('leagues.id'), nullable=False),
            sa.Column('owner_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
            sa.Column('player_id', sa.Integer, sa.ForeignKey('players.id'), nullable=False),
            sa.Column('season', sa.Integer, nullable=False),
            sa.Column('keep_cost', sa.Numeric, nullable=False),
            sa.Column('status', sa.String, nullable=False, server_default='pending'),
            sa.Column('flag_waiver', sa.Boolean, nullable=False, server_default='false'),
            sa.Column('flag_trade', sa.Boolean, nullable=False, server_default='false'),
            sa.Column('flag_drop', sa.Boolean, nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # transaction_history table
    if not inspector.has_table('transaction_history'):
        op.create_table(
            'transaction_history',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('league_id', sa.Integer, sa.ForeignKey('leagues.id'), nullable=False),
            sa.Column('player_id', sa.Integer, sa.ForeignKey('players.id'), nullable=False),
            sa.Column('old_owner_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
            sa.Column('new_owner_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
            sa.Column('transaction_type', sa.String, nullable=False),
            sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('notes', sa.String, nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('transaction_history'):
        op.drop_table('transaction_history')
    if inspector.has_table('keepers'):
        op.drop_table('keepers')
    if inspector.has_table('keeper_rules'):
        op.drop_table('keeper_rules')
