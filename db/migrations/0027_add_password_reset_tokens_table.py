"""0027 - add password_reset_tokens table

Secure account recovery support with:
- One-time use reset tokens
- Time-based token expiry
- Hashed token storage (SHA-256)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0027_add_password_reset_tokens_table"
down_revision = "0026_add_live_scoring_ingest_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "password_reset_tokens" in existing_tables:
        return

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer, primary_key=True, index=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_ip", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_unique_constraint(
        "uq_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
    )
    op.create_index(
        "ix_password_reset_tokens_user_id",
        "password_reset_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_password_reset_tokens_expires_at",
        "password_reset_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "password_reset_tokens" not in inspector.get_table_names():
        return

    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_constraint("uq_password_reset_tokens_token_hash", "password_reset_tokens", type_="unique")
    op.drop_table("password_reset_tokens")
