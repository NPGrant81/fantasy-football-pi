"""add economic ledger table

Revision ID: 20260302_01
Revises:
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260302_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economic_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=True),
        sa.Column("currency_type", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("from_owner_id", sa.Integer(), nullable=True),
        sa.Column("to_owner_id", sa.Integer(), nullable=True),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("reference_type", sa.String(), nullable=True),
        sa.Column("reference_id", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["from_owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["to_owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_economic_ledger_id"), "economic_ledger", ["id"], unique=False)
    op.create_index(op.f("ix_economic_ledger_league_id"), "economic_ledger", ["league_id"], unique=False)
    op.create_index(op.f("ix_economic_ledger_season_year"), "economic_ledger", ["season_year"], unique=False)
    op.create_index(op.f("ix_economic_ledger_currency_type"), "economic_ledger", ["currency_type"], unique=False)
    op.create_index(op.f("ix_economic_ledger_from_owner_id"), "economic_ledger", ["from_owner_id"], unique=False)
    op.create_index(op.f("ix_economic_ledger_to_owner_id"), "economic_ledger", ["to_owner_id"], unique=False)
    op.create_index(op.f("ix_economic_ledger_transaction_type"), "economic_ledger", ["transaction_type"], unique=False)
    op.create_index(op.f("ix_economic_ledger_reference_type"), "economic_ledger", ["reference_type"], unique=False)
    op.create_index(op.f("ix_economic_ledger_reference_id"), "economic_ledger", ["reference_id"], unique=False)
    op.create_index(op.f("ix_economic_ledger_created_by_user_id"), "economic_ledger", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_economic_ledger_created_at"), "economic_ledger", ["created_at"], unique=False)
    op.create_index("ix_economic_ledger_owner_lookup", "economic_ledger", ["league_id", "currency_type", "season_year", "to_owner_id", "from_owner_id"], unique=False)
    op.create_index("ix_economic_ledger_reference", "economic_ledger", ["reference_type", "reference_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_economic_ledger_reference", table_name="economic_ledger")
    op.drop_index("ix_economic_ledger_owner_lookup", table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_created_at"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_created_by_user_id"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_reference_id"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_reference_type"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_transaction_type"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_to_owner_id"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_from_owner_id"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_currency_type"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_season_year"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_league_id"), table_name="economic_ledger")
    op.drop_index(op.f("ix_economic_ledger_id"), table_name="economic_ledger")
    op.drop_table("economic_ledger")
