"""add mfl ingestion metadata tables"""

revision = '0018_add_mfl_ingestion_metadata_tables'
down_revision = '0017_add_target_league_id_to_mfl_html_record_facts'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'mfl_ingestion_runs' not in table_names:
        op.create_table(
            'mfl_ingestion_runs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('pipeline_stage', sa.String(length=32), nullable=False),
            sa.Column('source_system', sa.String(length=32), nullable=False, server_default='mfl'),
            sa.Column('target_league_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='running'),
            sa.Column('dry_run', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('truncate_before_load', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('input_roots', sa.JSON(), nullable=False),
            sa.Column('command', sa.String(), nullable=True),
            sa.Column('git_sha', sa.String(length=64), nullable=True),
            sa.Column('summary_json', sa.JSON(), nullable=True),
            sa.Column('notes', sa.String(), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['target_league_id'], ['leagues.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_mfl_ingestion_run_stage', 'mfl_ingestion_runs', ['pipeline_stage'], unique=False)
        op.create_index('ix_mfl_ingestion_run_target_league', 'mfl_ingestion_runs', ['target_league_id'], unique=False)
        op.create_index('ix_mfl_ingestion_run_status', 'mfl_ingestion_runs', ['status'], unique=False)
        op.alter_column('mfl_ingestion_runs', 'source_system', server_default=None)
        op.alter_column('mfl_ingestion_runs', 'status', server_default=None)
        op.alter_column('mfl_ingestion_runs', 'dry_run', server_default=None)
        op.alter_column('mfl_ingestion_runs', 'truncate_before_load', server_default=None)

    if 'mfl_ingestion_files' not in table_names:
        op.create_table(
            'mfl_ingestion_files',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('run_id', sa.Integer(), nullable=False),
            sa.Column('dataset_key', sa.String(length=80), nullable=False),
            sa.Column('season', sa.Integer(), nullable=True),
            sa.Column('source_league_id', sa.String(length=32), nullable=True),
            sa.Column('relative_path', sa.String(), nullable=False),
            sa.Column('content_type', sa.String(length=32), nullable=False, server_default='text/csv'),
            sa.Column('row_count', sa.Integer(), nullable=True),
            sa.Column('size_bytes', sa.Integer(), nullable=True),
            sa.Column('sha256', sa.String(length=64), nullable=True),
            sa.Column('retention_class', sa.String(length=32), nullable=True),
            sa.Column('archived_path', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.ForeignKeyConstraint(['run_id'], ['mfl_ingestion_runs.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('run_id', 'relative_path', name='uq_mfl_ingestion_file_run_path'),
        )
        op.create_index('ix_mfl_ingestion_file_run', 'mfl_ingestion_files', ['run_id'], unique=False)
        op.create_index('ix_mfl_ingestion_file_dataset', 'mfl_ingestion_files', ['dataset_key'], unique=False)
        op.create_index('ix_mfl_ingestion_file_source_league', 'mfl_ingestion_files', ['source_league_id'], unique=False)
        op.alter_column('mfl_ingestion_files', 'content_type', server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'mfl_ingestion_files' in table_names:
        index_names = {idx['name'] for idx in inspector.get_indexes('mfl_ingestion_files')}
        if 'ix_mfl_ingestion_file_source_league' in index_names:
            op.drop_index('ix_mfl_ingestion_file_source_league', table_name='mfl_ingestion_files')
        if 'ix_mfl_ingestion_file_dataset' in index_names:
            op.drop_index('ix_mfl_ingestion_file_dataset', table_name='mfl_ingestion_files')
        if 'ix_mfl_ingestion_file_run' in index_names:
            op.drop_index('ix_mfl_ingestion_file_run', table_name='mfl_ingestion_files')
        op.drop_table('mfl_ingestion_files')

    if 'mfl_ingestion_runs' in table_names:
        index_names = {idx['name'] for idx in inspector.get_indexes('mfl_ingestion_runs')}
        if 'ix_mfl_ingestion_run_status' in index_names:
            op.drop_index('ix_mfl_ingestion_run_status', table_name='mfl_ingestion_runs')
        if 'ix_mfl_ingestion_run_target_league' in index_names:
            op.drop_index('ix_mfl_ingestion_run_target_league', table_name='mfl_ingestion_runs')
        if 'ix_mfl_ingestion_run_stage' in index_names:
            op.drop_index('ix_mfl_ingestion_run_stage', table_name='mfl_ingestion_runs')
        op.drop_table('mfl_ingestion_runs')
