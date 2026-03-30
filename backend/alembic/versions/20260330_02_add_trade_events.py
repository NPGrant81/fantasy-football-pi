"""add trade_events audit timeline table

Revision ID: 20260330_02
Revises: 20260330_01
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260330_02"
down_revision = "20260330_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["trade_id"], ["trades.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trade_events_id"), "trade_events", ["id"], unique=False)
    op.create_index(op.f("ix_trade_events_trade_id"), "trade_events", ["trade_id"], unique=False)
    op.create_index(op.f("ix_trade_events_actor_user_id"), "trade_events", ["actor_user_id"], unique=False)
    op.create_index("ix_trade_events_trade_created", "trade_events", ["trade_id", "created_at"], unique=False)
    op.create_index("ix_trade_events_type", "trade_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trade_events_type", table_name="trade_events")
    op.drop_index("ix_trade_events_trade_created", table_name="trade_events")
    op.drop_index(op.f("ix_trade_events_actor_user_id"), table_name="trade_events")
    op.drop_index(op.f("ix_trade_events_trade_id"), table_name="trade_events")
    op.drop_index(op.f("ix_trade_events_id"), table_name="trade_events")
    op.drop_table("trade_events")
