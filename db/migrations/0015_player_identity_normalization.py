"""
player identity normalization phase 1
"""

revision = '0015_player_identity_normalization'
down_revision = ('0014_add_matchup_game_status', '5517dcbf0494')
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())

    if 'player_seasons' not in table_names:
        op.create_table(
            'player_seasons',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('player_id', sa.Integer(), nullable=False),
            sa.Column('season', sa.Integer(), nullable=False),
            sa.Column('nfl_team', sa.String(), nullable=True),
            sa.Column('position', sa.String(), nullable=True),
            sa.Column('bye_week', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('source', sa.String(length=32), nullable=False, server_default='bootstrap'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.ForeignKeyConstraint(['player_id'], ['players.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('player_id', 'season', name='uq_player_season'),
        )
        op.create_index('ix_player_seasons_season', 'player_seasons', ['season'], unique=False)

    if 'player_aliases' not in table_names:
        op.create_table(
            'player_aliases',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('player_id', sa.Integer(), nullable=False),
            sa.Column('alias_name', sa.String(), nullable=False),
            sa.Column('source', sa.String(length=32), nullable=False, server_default='canonical'),
            sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.ForeignKeyConstraint(['player_id'], ['players.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('player_id', 'alias_name', 'source', name='uq_player_alias_source'),
        )
        op.create_index('ix_player_aliases_alias_name', 'player_aliases', ['alias_name'], unique=False)

    # Bootstrap one season-state row from current players table values.
    op.execute(
        """
        INSERT INTO player_seasons (
            player_id,
            season,
            nfl_team,
            position,
            bye_week,
            is_active,
            source
        )
        SELECT
            p.id,
            EXTRACT(YEAR FROM CURRENT_DATE)::int,
            p.nfl_team,
            p.position,
            p.bye_week,
            TRUE,
            'bootstrap'
        FROM players p
        ON CONFLICT (player_id, season) DO NOTHING
        """
    )

    # Bootstrap canonical aliases from players.name.
    op.execute(
        """
        INSERT INTO player_aliases (
            player_id,
            alias_name,
            source,
            is_primary
        )
        SELECT
            p.id,
            p.name,
            'canonical',
            TRUE
        FROM players p
        WHERE p.name IS NOT NULL
          AND LENGTH(TRIM(p.name)) > 0
        ON CONFLICT (player_id, alias_name, source) DO NOTHING
        """
    )

    op.alter_column('player_seasons', 'source', server_default=None)
    op.alter_column('player_aliases', 'source', server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'player_aliases' in table_names:
        index_names = {idx['name'] for idx in inspector.get_indexes('player_aliases')}
        if 'ix_player_aliases_alias_name' in index_names:
            op.drop_index('ix_player_aliases_alias_name', table_name='player_aliases')
        op.drop_table('player_aliases')

    if 'player_seasons' in table_names:
        index_names = {idx['name'] for idx in inspector.get_indexes('player_seasons')}
        if 'ix_player_seasons_season' in index_names:
            op.drop_index('ix_player_seasons_season', table_name='player_seasons')
        op.drop_table('player_seasons')