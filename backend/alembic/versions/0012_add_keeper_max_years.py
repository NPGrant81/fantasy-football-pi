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
    op.add_column('keeper_rules', sa.Column('max_years_per_player', sa.Integer, nullable=False, server_default='1'))


def downgrade():
    op.drop_column('keeper_rules', 'max_years_per_player')
