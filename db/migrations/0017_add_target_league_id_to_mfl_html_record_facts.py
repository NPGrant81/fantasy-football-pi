"""add target_league_id to mfl_html_record_facts"""

revision = '0017_add_target_league_id_to_mfl_html_record_facts'
down_revision = '0016_add_mfl_html_record_facts'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'mfl_html_record_facts' not in table_names:
        return

    column_names = {column['name'] for column in inspector.get_columns('mfl_html_record_facts')}
    if 'target_league_id' not in column_names:
        op.add_column('mfl_html_record_facts', sa.Column('target_league_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_mfl_html_record_facts_target_league_id',
            'mfl_html_record_facts',
            'leagues',
            ['target_league_id'],
            ['id'],
        )

    index_names = {idx['name'] for idx in inspector.get_indexes('mfl_html_record_facts')}
    if 'ix_mfl_html_record_fact_target_league' not in index_names:
        op.create_index('ix_mfl_html_record_fact_target_league', 'mfl_html_record_facts', ['target_league_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'mfl_html_record_facts' not in table_names:
        return

    index_names = {idx['name'] for idx in inspector.get_indexes('mfl_html_record_facts')}
    if 'ix_mfl_html_record_fact_target_league' in index_names:
        op.drop_index('ix_mfl_html_record_fact_target_league', table_name='mfl_html_record_facts')

    foreign_keys = {fk['name'] for fk in inspector.get_foreign_keys('mfl_html_record_facts')}
    if 'fk_mfl_html_record_facts_target_league_id' in foreign_keys:
        op.drop_constraint('fk_mfl_html_record_facts_target_league_id', 'mfl_html_record_facts', type_='foreignkey')

    column_names = {column['name'] for column in inspector.get_columns('mfl_html_record_facts')}
    if 'target_league_id' in column_names:
        op.drop_column('mfl_html_record_facts', 'target_league_id')