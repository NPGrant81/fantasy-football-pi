"""add taxi flag to draft picks

Revision ID: 0008_add_taxi_flag
Revises: 0007_trade_future_dollars_and_budget
Create Date: 2026-02-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0008_add_taxi_flag'
down_revision = '0007_trade_future_dollars_and_budget'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('draft_picks')}

    # add a boolean column defaulting to false; existing rows will get false
    if 'is_taxi' not in columns:
        op.add_column('draft_picks', sa.Column('is_taxi', sa.Boolean(), nullable=False, server_default=sa.false()))

    # remove server_default after ensuring column exists
    op.alter_column('draft_picks', 'is_taxi', server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('draft_picks')}
    if 'is_taxi' in columns:
        op.drop_column('draft_picks', 'is_taxi')
