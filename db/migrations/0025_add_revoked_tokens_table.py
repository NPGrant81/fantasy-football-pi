"""0025 - add revoked_tokens table for JWT jti revocation

Adds persistent token revocation storage so logout/session invalidation survives
process restarts.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0025_add_revoked_tokens_table"
down_revision = "0024_add_validated_draft_results_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    if "revoked_tokens" in existing_tables:
        return

    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer, primary_key=True, index=True, autoincrement=True),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("token_subject", sa.String(length=255), nullable=True),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_unique_constraint("uq_revoked_tokens_jti", "revoked_tokens", ["jti"])
    op.create_index("ix_revoked_tokens_jti", "revoked_tokens", ["jti"])
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "revoked_tokens" not in inspector.get_table_names():
        return

    op.drop_index("ix_revoked_tokens_expires_at", table_name="revoked_tokens")
    op.drop_index("ix_revoked_tokens_jti", table_name="revoked_tokens")
    op.drop_constraint("uq_revoked_tokens_jti", "revoked_tokens", type_="unique")
    op.drop_table("revoked_tokens")
