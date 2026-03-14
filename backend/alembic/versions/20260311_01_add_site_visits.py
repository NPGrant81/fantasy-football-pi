"""add site_visits table

Revision ID: 20260311_01
Revises: 20260307_01
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260311_01"
down_revision = "20260307_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_visits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("referrer", sa.String(), nullable=True),
        sa.Column("client_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_site_visits_path", "site_visits", ["path"])
    op.create_index("ix_site_visits_session_id", "site_visits", ["session_id"])
    op.create_index("ix_site_visits_timestamp", "site_visits", ["timestamp"])
    op.create_index("ix_site_visits_user_id", "site_visits", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_site_visits_user_id", table_name="site_visits")
    op.drop_index("ix_site_visits_timestamp", table_name="site_visits")
    op.drop_index("ix_site_visits_session_id", table_name="site_visits")
    op.drop_index("ix_site_visits_path", table_name="site_visits")
    op.drop_table("site_visits")
