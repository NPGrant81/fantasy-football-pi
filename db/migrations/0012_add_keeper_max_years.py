"""
Add maximum years per player to keeper_rules
"""
revision = '0012_add_keeper_max_years'
down_revision = '0011_extend_keeper_table_with_locking_and_tracking'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('keeper_rules')}
    if 'max_years_per_player' not in columns:
        op.add_column('keeper_rules', sa.Column('max_years_per_player', sa.Integer, nullable=False, server_default='1'))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('keeper_rules')}
    if 'max_years_per_player' in columns:
        op.drop_column('keeper_rules', 'max_years_per_player')
