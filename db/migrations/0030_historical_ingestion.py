"""Own historical source identities, seasonal budgets and archival accounts.

Revision ID: 0030_historical_ingestion
Revises: 0028_reconcile_runtime_schema
"""

from alembic import op
import sqlalchemy as sa

revision = "0030_historical_ingestion"
down_revision = "0028_reconcile_runtime_schema"
branch_labels = None
depends_on = None


def _column(table: str, column: sa.Column) -> None:
    columns = {row["name"]: row for row in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in columns:
        op.add_column(table, column)
    elif (
        not isinstance(columns[column.name]["type"], type(column.type))
        or getattr(columns[column.name]["type"], "length", None)
        != getattr(column.type, "length", None)
        or columns[column.name]["nullable"] != column.nullable
    ):
        raise RuntimeError(
            f"Incompatible existing historical column: {table}.{column.name}"
        )


def upgrade() -> None:
    # Retain legacy evidence in place; these are not active configuration fields.
    legacy_columns = {
        "keepers": [
            ("draft_year", sa.Integer()),
            ("trade_deadline", sa.String()),
            ("waiver_system", sa.String()),
            ("playoff_qualifiers", sa.Integer()),
            ("starting_waiver_budget", sa.Integer()),
            ("playoff_reseed", sa.Boolean()),
            ("playoff_consolation", sa.Boolean()),
            ("waiver_tiebreaker", sa.String()),
            ("playoff_tiebreakers", sa.JSON()),
            ("waiver_deadline", sa.String()),
        ],
        "manual_player_mappings": [
            ("true_player_id", sa.Integer()),
            ("scraped_player_name", sa.String()),
            ("source_name", sa.String()),
        ],
        "player_seasons": [("mfl_id", sa.String(32))],
        "scoring_rules": [("points", sa.Float())],
    }
    for table, columns in legacy_columns.items():
        existing = {
            row["name"]: row for row in sa.inspect(op.get_bind()).get_columns(table)
        }
        for name, kind in columns:
            if name in existing and not existing[name]["nullable"]:
                op.alter_column(
                    table, name, existing_type=existing[name]["type"], nullable=True
                )
            _column(table, sa.Column(name, kind, nullable=True))
    _column("users", sa.Column("division", sa.String(), nullable=True))
    _column(
        "users",
        sa.Column(
            "is_historical_stub",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    for name in ("mfl_id", "sleeper_id"):
        _column("players", sa.Column(name, sa.String(32), nullable=True))
    for table, identifier in (
        ("draft_picks", "source_event_id"),
        ("transaction_history", "source_transaction_id"),
    ):
        _column(table, sa.Column("source", sa.String(32), nullable=True))
        _column(table, sa.Column(identifier, sa.String(128), nullable=True))
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints("waiver_budgets"):
        if constraint["name"] == "uq_waiver_league_owner":
            op.drop_constraint(constraint["name"], "waiver_budgets", type_="unique")
    if not any(
        row["name"] == "uq_waiver_budget_league_owner_year"
        for row in sa.inspect(op.get_bind()).get_unique_constraints("waiver_budgets")
    ):
        op.create_unique_constraint(
            "uq_waiver_budget_league_owner_year",
            "waiver_budgets",
            ["league_id", "owner_id", "year"],
        )
    indexes = [
        ("players", "ix_players_mfl_id", ["mfl_id"], True, None),
        ("players", "ix_players_sleeper_id", ["sleeper_id"], True, None),
        ("users", "ix_users_is_historical_stub", ["is_historical_stub"], False, None),
        ("draft_picks", "ix_draft_picks_year", ["year"], False, None),
        (
            "draft_picks",
            "ix_draft_picks_league_year",
            ["league_id", "year"],
            False,
            None,
        ),
        (
            "waiver_budgets",
            "ix_waiver_budgets_league_year_owner",
            ["league_id", "year", "owner_id"],
            False,
            None,
        ),
        (
            "draft_picks",
            "uq_draft_picks_league_source_event",
            ["league_id", "source", "source_event_id"],
            True,
            "source_event_id IS NOT NULL",
        ),
        (
            "transaction_history",
            "uq_transaction_history_source_event",
            ["league_id", "source", "source_transaction_id"],
            True,
            "source_transaction_id IS NOT NULL",
        ),
    ]
    for table, name, columns, unique, predicate in indexes:
        existing = {row["name"] for row in sa.inspect(op.get_bind()).get_indexes(table)}
        if name not in existing:
            options = {"postgresql_where": sa.text(predicate)} if predicate else {}
            op.create_index(name, table, columns, unique=unique, **options)
    for table, identifier in (
        ("draft_picks", "source_event_id"),
        ("transaction_history", "source_transaction_id"),
    ):
        name = f"ck_{table}_source_identity"
        if name not in {
            row["name"]
            for row in sa.inspect(op.get_bind()).get_check_constraints(table)
        }:
            op.create_check_constraint(
                name,
                table,
                f"{identifier} IS NULL OR (league_id IS NOT NULL AND source IS NOT NULL "
                f"AND length(trim(source)) > 0 AND length(trim({identifier})) > 0)",
            )
    users = sa.table(
        "users", sa.column("username"), sa.column("is_historical_stub", sa.Boolean())
    )
    op.get_bind().execute(
        users.update()
        .where(sa.func.lower(users.c.username).startswith("hist_", autoescape=True))
        .values(is_historical_stub=True)
    )


def downgrade() -> None:
    raise RuntimeError(
        "Historical schema adoption is forward-only; restore a verified backup."
    )
