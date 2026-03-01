"""
add division_id column to users
"""
revision = '0004_add_division_to_users'
down_revision = '0003_complex_scoring_rules'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('users', sa.Column('division_id', sa.Integer, nullable=True))
    op.create_foreign_key(
        'fk_users_division', 'users', 'divisions', ['division_id'], ['id'], ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_users_division', 'users', type_='foreignkey')
    op.drop_column('users', 'division_id')
