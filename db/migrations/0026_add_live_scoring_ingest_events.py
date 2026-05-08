"""0026 – add live_scoring_ingest_events table

Persists one row per unique live scoring ingest fingerprint scope
(source + season + week + fingerprint).

Purpose:
- Durable audit trail for applied live scoring updates
- Replay/idempotency guard so repeated ingests with the same fingerprint
  do not re-trigger downstream write flows
- Store fetch diagnostics and raw payload pointer for debugging
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0026_add_live_scoring_ingest_events"
down_revision = "0025_add_player_injury_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "live_scoring_ingest_events" in existing_tables:
        return

    op.create_table(
        "live_scoring_ingest_events",
        sa.Column("id", sa.Integer, primary_key=True, index=True, autoincrement=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("season", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=True),
        sa.Column("scoreboard_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("event_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("game_states", sa.JSON(), nullable=True),
        sa.Column("fetch_diagnostics", sa.JSON(), nullable=True),
        sa.Column("raw_response_path", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_unique_constraint(
        "uq_live_scoring_ingest_event_scope",
        "live_scoring_ingest_events",
        ["source", "season", "week", "scoreboard_fingerprint"],
    )
    op.create_index(
        "ix_live_scoring_ingest_events_scope",
        "live_scoring_ingest_events",
        ["source", "season", "week"],
    )
    op.create_index(
        "ix_live_scoring_ingest_events_fingerprint",
        "live_scoring_ingest_events",
        ["scoreboard_fingerprint"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "live_scoring_ingest_events" not in inspector.get_table_names():
        return

    op.drop_index("ix_live_scoring_ingest_events_fingerprint", table_name="live_scoring_ingest_events")
    op.drop_index("ix_live_scoring_ingest_events_scope", table_name="live_scoring_ingest_events")
    op.drop_constraint("uq_live_scoring_ingest_event_scope", "live_scoring_ingest_events", type_="unique")
    op.drop_table("live_scoring_ingest_events")
