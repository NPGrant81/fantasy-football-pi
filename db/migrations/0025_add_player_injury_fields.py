"""0025 – add injury / availability fields to players table

Adds four optional columns to track current injury status, free-text notes,
and projected return timeline.  All columns are nullable so existing rows are
unaffected; NULL means the player is healthy / status unknown.

Injury status vocabulary (stored as uppercase strings):
  OUT          – ruled out for the current week
  IR           – placed on Injured Reserve; season-ending or multi-week
  DOUBTFUL     – high likelihood of missing the game
  QUESTIONABLE – may or may not play; monitor status
  LIMITED      – practising in a limited capacity; likely to play
  NULL         – no designation / fully healthy
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0025_add_player_injury_fields"
down_revision = "0024_add_validated_draft_results_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {c["name"] for c in inspector.get_columns("players")}

    if "injury_status" not in existing_cols:
        op.add_column("players", sa.Column("injury_status", sa.String, nullable=True))
    if "injury_notes" not in existing_cols:
        op.add_column("players", sa.Column("injury_notes", sa.String, nullable=True))
    if "projected_return_date" not in existing_cols:
        op.add_column("players", sa.Column("projected_return_date", sa.String, nullable=True))
    if "projected_return_week" not in existing_cols:
        op.add_column("players", sa.Column("projected_return_week", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("players", "projected_return_week")
    op.drop_column("players", "projected_return_date")
    op.drop_column("players", "injury_notes")
    op.drop_column("players", "injury_status")
