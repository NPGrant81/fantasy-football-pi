"""reconcile runtime-managed columns under Alembic ownership

Revision ID: 0028_reconcile_runtime_schema
Revises: 0023_add_owner_season_behavior_table, 0025_add_revoked_tokens_table,
    0027_add_admin_audit_logs_table, 0027_add_password_reset_tokens_table
"""

from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa


revision = "0028_reconcile_runtime_schema"
down_revision = (
    "0023_add_owner_season_behavior_table",
    "0025_add_revoked_tokens_table",
    "0027_add_admin_audit_logs_table",
    "0027_add_password_reset_tokens_table",
)
branch_labels = None
depends_on = None


def _add_missing_columns(table_name: str, columns: Iterable[sa.Column]) -> None:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns(table_name)}
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def _ensure_foreign_key(
    table_name: str,
    column_name: str,
    referred_table: str,
    constraint_name: str,
) -> None:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return

    foreign_keys = inspector.get_foreign_keys(table_name)
    if any(
        foreign_key.get("constrained_columns") == [column_name]
        and foreign_key.get("referred_table") == referred_table
        for foreign_key in foreign_keys
    ):
        return

    op.create_foreign_key(
        constraint_name,
        table_name,
        referred_table,
        [column_name],
        ["id"],
    )


def _ensure_index(table_name: str, index_name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return

    existing = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    _add_missing_columns(
        "league_settings",
        (
            sa.Column("draft_year", sa.Integer(), nullable=True),
            sa.Column("trade_deadline", sa.String(), nullable=True),
            sa.Column("starting_waiver_budget", sa.Integer(), server_default="100", nullable=True),
            sa.Column("waiver_system", sa.String(), nullable=True),
            sa.Column("waiver_tiebreaker", sa.String(), nullable=True),
            sa.Column("playoff_qualifiers", sa.Integer(), server_default="6", nullable=True),
            sa.Column("playoff_reseed", sa.Boolean(), server_default=sa.false(), nullable=True),
            sa.Column("playoff_consolation", sa.Boolean(), server_default=sa.true(), nullable=True),
            sa.Column(
                "playoff_tiebreakers",
                sa.JSON(),
                server_default=sa.text(
                    "'[]'::json"
                ),
                nullable=True,
            ),
            sa.Column("future_draft_cap", sa.Integer(), server_default="0", nullable=True),
            sa.Column("divisions_enabled", sa.Boolean(), server_default=sa.false(), nullable=True),
            sa.Column("division_count", sa.Integer(), nullable=True),
            sa.Column("division_config_status", sa.String(), server_default="draft", nullable=True),
            sa.Column("division_assignment_method", sa.String(), nullable=True),
            sa.Column("division_random_seed", sa.String(), nullable=True),
            sa.Column("division_needs_reseed", sa.Boolean(), server_default=sa.false(), nullable=True),
            sa.Column("division_history_enabled", sa.Boolean(), server_default=sa.true(), nullable=True),
            sa.Column("trade_start_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("trade_end_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("allow_playoff_trades", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column(
                "require_commissioner_approval",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            ),
            sa.Column("trade_veto_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("trade_veto_threshold", sa.Integer(), nullable=True),
            sa.Column("trade_review_period_hours", sa.Integer(), nullable=True),
            sa.Column("trade_max_players_per_side", sa.Integer(), nullable=True),
            sa.Column(
                "trade_league_vote_enabled",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
            sa.Column("trade_league_vote_threshold", sa.Integer(), nullable=True),
        ),
    )
    _add_missing_columns(
        "scoring_rules",
        (
            sa.Column("season_year", sa.Integer(), nullable=True),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("position_ids", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
            sa.Column("source", sa.String(32), server_default="custom", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("template_id", sa.Integer(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        ),
    )
    _add_missing_columns(
        "users",
        (
            sa.Column("division_id", sa.Integer(), nullable=True),
            sa.Column("future_draft_budget", sa.Integer(), server_default="0", nullable=True),
        ),
    )
    _add_missing_columns(
        "divisions",
        (
            sa.Column("season", sa.Integer(), nullable=True),
            sa.Column("order_index", sa.Integer(), server_default="0", nullable=True),
        ),
    )
    _add_missing_columns(
        "draft_picks",
        (sa.Column("is_taxi", sa.Boolean(), server_default=sa.false(), nullable=True),),
    )
    _add_missing_columns(
        "keeper_rules",
        (sa.Column("max_years_per_player", sa.Integer(), server_default="1", nullable=True),),
    )
    _add_missing_columns(
        "keepers",
        (
            sa.Column("years_kept_count", sa.Integer(), server_default="1", nullable=True),
            sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_by_commish", sa.Boolean(), server_default=sa.false(), nullable=True),
        ),
    )
    _add_missing_columns(
        "matchups",
        (
            sa.Column("is_division_matchup", sa.Boolean(), server_default=sa.false(), nullable=True),
            sa.Column("is_rivalry_week", sa.Boolean(), server_default=sa.false(), nullable=True),
            sa.Column("rivalry_name", sa.String(), nullable=True),
        ),
    )
    _add_missing_columns(
        "playoff_matches",
        (
            sa.Column("team_1_seed", sa.Integer(), nullable=True),
            sa.Column("team_2_seed", sa.Integer(), nullable=True),
            sa.Column(
                "team_1_is_division_winner",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=True,
            ),
            sa.Column(
                "team_2_is_division_winner",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=True,
            ),
        ),
    )
    _add_missing_columns(
        "draft_values",
        (
            sa.Column("avg_bid", sa.Float(), nullable=True),
            sa.Column("median_bid", sa.Float(), nullable=True),
            sa.Column("recent_3yr_avg", sa.Float(), nullable=True),
            sa.Column("trend_slope", sa.Float(), nullable=True),
            sa.Column("appearances", sa.Integer(), nullable=True),
            sa.Column("model_score", sa.Float(), nullable=True),
            sa.Column("rank", sa.Integer(), nullable=True),
        ),
    )
    _add_missing_columns(
        "manual_player_mappings",
        (
            sa.Column("scraped_name", sa.String(), nullable=True),
            sa.Column("player_id", sa.Integer(), nullable=True),
            sa.Column("mapped_at", sa.String(), nullable=True),
            sa.Column("team", sa.String(), nullable=True),
            sa.Column("position", sa.String(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
        ),
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "manual_player_mappings" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("manual_player_mappings")}
        if "scraped_player_name" in columns:
            op.execute(
                sa.text(
                    "UPDATE manual_player_mappings SET scraped_name = scraped_player_name "
                    "WHERE scraped_name IS NULL"
                )
            )
        if "true_player_id" in columns:
            op.execute(
                sa.text(
                    "UPDATE manual_player_mappings SET player_id = true_player_id "
                    "WHERE player_id IS NULL"
                )
            )

    _ensure_foreign_key("users", "division_id", "divisions", "fk_users_division_id")
    _ensure_foreign_key(
        "scoring_rules",
        "template_id",
        "scoring_templates",
        "fk_scoring_rules_template_id",
    )
    _ensure_foreign_key(
        "scoring_rules",
        "created_by_user_id",
        "users",
        "fk_scoring_rules_created_by_user_id",
    )
    _ensure_foreign_key(
        "scoring_rules",
        "updated_by_user_id",
        "users",
        "fk_scoring_rules_updated_by_user_id",
    )
    _ensure_foreign_key(
        "manual_player_mappings",
        "player_id",
        "players",
        "fk_manual_player_mappings_player_id",
    )

    _ensure_index("divisions", "ix_divisions_season", ["season"])
    _ensure_index("scoring_rules", "ix_scoring_rules_season_year", ["season_year"])
    _ensure_index(
        "scoring_rules",
        "ix_scoring_rules_lookup",
        ["league_id", "season_year", "is_active", "event_name"],
    )
    _ensure_index(
        "manual_player_mappings",
        "ix_manual_player_mappings_scraped_name",
        ["scraped_name"],
    )


def downgrade() -> None:
    # This reconciliation adopts columns that may predate Alembic ownership.
    # Dropping them would destroy valid production data, so downgrade is a no-op.
    pass
