"""0027 - add admin_audit_logs table for privileged action auditing

Creates immutable audit storage for commissioner/superuser privileged actions.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0027_add_admin_audit_logs_table"
down_revision = "0026_add_refresh_tokens_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    if "admin_audit_logs" in existing_tables:
        return

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True, autoincrement=True),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_username", sa.String(length=255), nullable=False),
        sa.Column("actor_is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("actor_is_commissioner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("league_id", sa.Integer, sa.ForeignKey("leagues.id"), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])
    op.create_index("ix_admin_audit_logs_actor_user_id", "admin_audit_logs", ["actor_user_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "admin_audit_logs" not in inspector.get_table_names():
        return

    op.drop_index("ix_admin_audit_logs_actor_user_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
