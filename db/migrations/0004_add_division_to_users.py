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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column['name'] for column in inspector.get_columns('users')}

    if 'division_id' not in user_columns:
        op.add_column('users', sa.Column('division_id', sa.Integer, nullable=True))

    foreign_keys = inspector.get_foreign_keys('users')
    has_fk = any(
        fk.get('name') == 'fk_users_division'
        or (fk.get('constrained_columns') == ['division_id'] and fk.get('referred_table') == 'divisions')
        for fk in foreign_keys
    )
    if not has_fk:
        op.create_foreign_key(
            'fk_users_division', 'users', 'divisions', ['division_id'], ['id'], ondelete='SET NULL'
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    foreign_keys = inspector.get_foreign_keys('users')
    if any(fk.get('name') == 'fk_users_division' for fk in foreign_keys):
        op.drop_constraint('fk_users_division', 'users', type_='foreignkey')

    user_columns = {column['name'] for column in inspector.get_columns('users')}
    if 'division_id' in user_columns:
        op.drop_column('users', 'division_id')
