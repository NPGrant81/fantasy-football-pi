"""add mfl_html_record_facts table"""

revision = '0016_add_mfl_html_record_facts'
down_revision = '0015_player_identity_normalization'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'mfl_html_record_facts' not in table_names:
        op.create_table(
            'mfl_html_record_facts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('dataset_key', sa.String(length=80), nullable=False),
            sa.Column('season', sa.Integer(), nullable=True),
            sa.Column('league_id', sa.String(length=32), nullable=True),
            sa.Column('source_endpoint', sa.String(length=80), nullable=True),
            sa.Column('source_url', sa.String(), nullable=True),
            sa.Column('extracted_at_utc', sa.String(), nullable=True),
            sa.Column('normalization_version', sa.String(length=16), nullable=False, server_default='v1'),
            sa.Column('row_fingerprint', sa.String(length=64), nullable=False),
            sa.Column('record_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('dataset_key', 'row_fingerprint', name='uq_mfl_html_record_fact_dataset_fingerprint'),
        )

        op.create_index('ix_mfl_html_record_fact_dataset', 'mfl_html_record_facts', ['dataset_key'], unique=False)
        op.create_index('ix_mfl_html_record_fact_season', 'mfl_html_record_facts', ['season'], unique=False)
        op.create_index('ix_mfl_html_record_fact_league', 'mfl_html_record_facts', ['league_id'], unique=False)

        op.alter_column('mfl_html_record_facts', 'normalization_version', server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'mfl_html_record_facts' in table_names:
        index_names = {idx['name'] for idx in inspector.get_indexes('mfl_html_record_facts')}
        if 'ix_mfl_html_record_fact_league' in index_names:
            op.drop_index('ix_mfl_html_record_fact_league', table_name='mfl_html_record_facts')
        if 'ix_mfl_html_record_fact_season' in index_names:
            op.drop_index('ix_mfl_html_record_fact_season', table_name='mfl_html_record_facts')
        if 'ix_mfl_html_record_fact_dataset' in index_names:
            op.drop_index('ix_mfl_html_record_fact_dataset', table_name='mfl_html_record_facts')
        op.drop_table('mfl_html_record_facts')
