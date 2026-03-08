"""scoring rules schema foundation

Revision ID: 20260307_01
Revises: 20260302_01
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260307_01"
down_revision = "20260302_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scoring_rules", sa.Column("season_year", sa.Integer(), nullable=True))
    op.add_column("scoring_rules", sa.Column("position_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.add_column("scoring_rules", sa.Column("source", sa.String(length=32), nullable=False, server_default="custom"))
    op.add_column("scoring_rules", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("scoring_rules", sa.Column("template_id", sa.Integer(), nullable=True))
    op.add_column("scoring_rules", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.add_column("scoring_rules", sa.Column("updated_by_user_id", sa.Integer(), nullable=True))
    op.add_column("scoring_rules", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_scoring_rules_created_by_user_id",
        "scoring_rules",
        "users",
        ["created_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_scoring_rules_updated_by_user_id",
        "scoring_rules",
        "users",
        ["updated_by_user_id"],
        ["id"],
    )

    op.create_index("ix_scoring_rules_lookup", "scoring_rules", ["league_id", "season_year", "is_active", "event_name"], unique=False)

    op.create_table(
        "scoring_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("source_platform", sa.String(length=32), nullable=False, server_default="custom"),
        sa.Column("is_system_template", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "name", "season_year", name="uq_scoring_template_league_name_season"),
    )
    op.create_index("ix_scoring_templates_lookup", "scoring_templates", ["league_id", "season_year", "is_active"], unique=False)

    op.create_foreign_key(
        "fk_scoring_rules_template_id",
        "scoring_rules",
        "scoring_templates",
        ["template_id"],
        ["id"],
    )

    op.create_table(
        "scoring_template_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("scoring_rule_id", sa.Integer(), nullable=False),
        sa.Column("rule_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("included", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["template_id"], ["scoring_templates.id"]),
        sa.ForeignKeyConstraint(["scoring_rule_id"], ["scoring_rules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "scoring_rule_id", name="uq_scoring_template_rule_link"),
    )
    op.create_index("ix_scoring_template_rules_template_order", "scoring_template_rules", ["template_id", "rule_order"], unique=False)

    op.create_table(
        "scoring_rule_change_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("scoring_rule_id", sa.Integer(), nullable=True),
        sa.Column("season_year", sa.Integer(), nullable=True),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.String(), nullable=True),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("changed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["scoring_rule_id"], ["scoring_rules.id"]),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scoring_rule_change_logs_lookup", "scoring_rule_change_logs", ["league_id", "season_year", "changed_at"], unique=False)

    op.create_table(
        "scoring_rule_proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("proposed_change", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("proposed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("voting_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_by_user_id", sa.Integer(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["proposed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["finalized_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scoring_rule_proposals_lookup", "scoring_rule_proposals", ["league_id", "season_year", "status", "created_at"], unique=False)

    op.create_table(
        "scoring_rule_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proposal_id", sa.Integer(), nullable=False),
        sa.Column("voter_user_id", sa.Integer(), nullable=False),
        sa.Column("vote", sa.String(length=16), nullable=False),
        sa.Column("vote_weight", sa.Numeric(6, 2), nullable=False, server_default="1"),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["proposal_id"], ["scoring_rule_proposals.id"]),
        sa.ForeignKeyConstraint(["voter_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", "voter_user_id", name="uq_scoring_rule_votes_proposal_voter"),
    )


    # Normalize pre-existing rows for new non-nullable columns.
    op.execute("UPDATE scoring_rules SET source = 'custom' WHERE source IS NULL")
    op.execute("UPDATE scoring_rules SET is_active = TRUE WHERE is_active IS NULL")
    op.execute("UPDATE scoring_rules SET position_ids = '[]'::json WHERE position_ids IS NULL")


    op.alter_column("scoring_rules", "position_ids", server_default=None)
    op.alter_column("scoring_rules", "source", server_default=None)
    op.alter_column("scoring_rules", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_scoring_rules_lookup", table_name="scoring_rules")
    op.drop_constraint("fk_scoring_rules_updated_by_user_id", "scoring_rules", type_="foreignkey")
    op.drop_constraint("fk_scoring_rules_created_by_user_id", "scoring_rules", type_="foreignkey")
    op.drop_constraint("fk_scoring_rules_template_id", "scoring_rules", type_="foreignkey")

    op.drop_table("scoring_rule_votes")

    op.drop_index("ix_scoring_rule_proposals_lookup", table_name="scoring_rule_proposals")
    op.drop_table("scoring_rule_proposals")

    op.drop_index("ix_scoring_rule_change_logs_lookup", table_name="scoring_rule_change_logs")
    op.drop_table("scoring_rule_change_logs")

    op.drop_index("ix_scoring_template_rules_template_order", table_name="scoring_template_rules")
    op.drop_table("scoring_template_rules")

    op.drop_index("ix_scoring_templates_lookup", table_name="scoring_templates")
    op.drop_table("scoring_templates")

    op.drop_column("scoring_rules", "deactivated_at")
    op.drop_column("scoring_rules", "updated_by_user_id")
    op.drop_column("scoring_rules", "created_by_user_id")
    op.drop_column("scoring_rules", "template_id")
    op.drop_column("scoring_rules", "is_active")
    op.drop_column("scoring_rules", "source")
    op.drop_column("scoring_rules", "position_ids")
    op.drop_column("scoring_rules", "season_year")
