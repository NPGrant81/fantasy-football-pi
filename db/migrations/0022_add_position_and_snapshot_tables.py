"""
issue #103 phase 2: position registry and canonical player snapshot tables
"""

revision = '0022_add_position_and_snapshot_tables'
down_revision = '0021_add_league_settings_trade_governance_columns'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


# Canonical active positions seeded into the positions table on first run.
_ACTIVE_POSITIONS = [
    ("QB",   "Quarterback",    True,  1),
    ("RB",   "Running Back",   True,  2),
    ("WR",   "Wide Receiver",  True,  3),
    ("TE",   "Tight End",      True,  4),
    ("K",    "Kicker",         True,  5),
    ("DEF",  "Defense/ST",     True,  6),
    ("FLEX", "Flex",           True,  7),
]

# Legacy/inactive position tokens that may exist in historical data.
_INACTIVE_POSITIONS = [
    ("D/ST",    "Defense/ST (legacy)",   False, None),
    ("DST",     "Defense/ST (alt)",      False, None),
    ("DEFENSE", "Defense (verbose)",     False, None),
    ("TD",      "TD (legacy MFL)",       False, None),
    ("PK",      "Kicker (legacy MFL)",   False, None),
    ("KICKER",  "Kicker (verbose)",      False, None),
    ("UNKNOWN", "Unknown",               False, None),
]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    # ------------------------------------------------------------------
    # 1. positions table
    # ------------------------------------------------------------------
    if 'positions' not in table_names:
        op.create_table(
            'positions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('abbreviation', sa.String(8), nullable=False),
            sa.Column('label', sa.String(64), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('source', sa.String(32), nullable=False, server_default='canonical'),
            sa.Column('sort_order', sa.Integer(), nullable=True),
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text('now()'),
            ),
            sa.Column(
                'updated_at',
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text('now()'),
            ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('abbreviation', name='uq_positions_abbreviation'),
        )
        op.create_index('ix_positions_abbreviation', 'positions', ['abbreviation'], unique=True)

        # Seed active positions
        positions_table = sa.table(
            'positions',
            sa.column('abbreviation', sa.String),
            sa.column('label', sa.String),
            sa.column('is_active', sa.Boolean),
            sa.column('source', sa.String),
            sa.column('sort_order', sa.Integer),
        )
        rows = [
            {'abbreviation': abbr, 'label': label, 'is_active': active, 'source': 'canonical', 'sort_order': sort}
            for abbr, label, active, sort in _ACTIVE_POSITIONS + _INACTIVE_POSITIONS
        ]
        op.bulk_insert(positions_table, rows)

    # ------------------------------------------------------------------
    # 2. canonical_player_snapshots table
    # ------------------------------------------------------------------
    if 'canonical_player_snapshots' not in table_names:
        op.create_table(
            'canonical_player_snapshots',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('season', sa.Integer(), nullable=False),
            sa.Column('content_digest', sa.String(64), nullable=False),
            sa.Column('total_rows', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('unique_player_ids', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('deduplicated_rows', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('duplicate_name_keys', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('position_distribution', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('source', sa.String(32), nullable=False, server_default='etl_build'),
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text('now()'),
            ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('season', 'content_digest', name='uq_snapshot_season_digest'),
        )
        op.create_index('ix_canonical_player_snapshot_season', 'canonical_player_snapshots', ['season'])
        op.create_index('ix_canonical_player_snapshot_created', 'canonical_player_snapshots', ['created_at'])


def downgrade():
    op.drop_table('canonical_player_snapshots')
    op.drop_table('positions')
