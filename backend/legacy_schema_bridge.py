"""Explicit, forward-only adoption of the pinned pre-Alembic PostgreSQL schema."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.schema import CreateSchema, DropSchema


LEGACY_SCHEMA = "public"
ARCHIVE_SCHEMA = "ffpi_legacy_archive"
STATE_TABLE = "adoption_state"
LEGACY_TABLES = frozenset(
    {
        "bug_reports",
        "draft_budgets",
        "draft_picks",
        "leagues",
        "league_settings",
        "lineup_submissions",
        "matchups",
        "player_weekly_stats",
        "players",
        "scoring_rules",
        "trade_proposals",
        "users",
        "waiver_claims",
    }
)
LEGACY_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "db"
    / "test_fixtures"
    / "pre_0001_legacy_schema.sql"
)


@dataclass(frozen=True)
class LegacyAdoptionReport:
    database: str | None
    phase: str
    table_row_counts: tuple[tuple[str, int], ...]
    scoring_rule_rows: int
    division_groups: int


def _quoted(connection: Connection, identifier: str) -> str:
    return connection.dialect.identifier_preparer.quote(identifier)


def _qualified(connection: Connection, schema: str, identifier: str) -> str:
    return f"{_quoted(connection, schema)}.{_quoted(connection, identifier)}"


def _normalize_schema_expression(value: object, schema: str) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        return re.sub(rf'"?{re.escape(schema)}"?\.', "", value)
    if isinstance(value, (tuple, list)):
        return tuple(_normalize_schema_expression(item, schema) for item in value)
    return value


def _schema_snapshot(connection: Connection, schema: str) -> dict[str, object]:
    inspector = inspect(connection)
    snapshot: dict[str, object] = {}
    table_names = sorted(inspector.get_table_names(schema=schema))
    for table_name in table_names:
        columns = tuple(
            sorted(
                (
                    column["name"],
                    column["type"].compile(dialect=connection.dialect),
                    column["nullable"],
                    _normalize_schema_expression(column.get("default"), schema),
                )
                for column in inspector.get_columns(table_name, schema=schema)
            )
        )
        primary_key = inspector.get_pk_constraint(table_name, schema=schema)
        foreign_keys = tuple(
            sorted(
                [
                    (
                        foreign_key.get("name"),
                        tuple(foreign_key.get("constrained_columns") or ()),
                        foreign_key.get("referred_table"),
                        tuple(foreign_key.get("referred_columns") or ()),
                        tuple(sorted((foreign_key.get("options") or {}).items())),
                    )
                    for foreign_key in inspector.get_foreign_keys(
                        table_name,
                        schema=schema,
                    )
                ],
                key=repr,
            )
        )
        unique_constraints = tuple(
            sorted(
                [
                    (
                        constraint.get("name"),
                        tuple(constraint.get("column_names") or ()),
                    )
                    for constraint in inspector.get_unique_constraints(
                        table_name,
                        schema=schema,
                    )
                ],
                key=repr,
            )
        )
        check_constraints = tuple(
            sorted(
                [
                    (
                        constraint.get("name"),
                        _normalize_schema_expression(
                            constraint.get("sqltext"),
                            schema,
                        ),
                    )
                    for constraint in inspector.get_check_constraints(
                        table_name,
                        schema=schema,
                    )
                ],
                key=repr,
            )
        )
        indexes = tuple(
            sorted(
                [
                    (
                        index.get("name"),
                        tuple(index.get("column_names") or ()),
                        index.get("unique"),
                        _normalize_schema_expression(
                            index.get("expressions"),
                            schema,
                        ),
                        tuple(
                            sorted(
                                (key, str(value))
                                for key, value in (
                                    index.get("dialect_options") or {}
                                ).items()
                            )
                        ),
                    )
                    for index in inspector.get_indexes(table_name, schema=schema)
                ],
                key=repr,
            )
        )
        snapshot[table_name] = {
            "columns": columns,
            "primary_key": (
                primary_key.get("name"),
                tuple(primary_key.get("constrained_columns") or ()),
            ),
            "foreign_keys": foreign_keys,
            "unique_constraints": unique_constraints,
            "check_constraints": check_constraints,
            "indexes": indexes,
        }
    snapshot["sequences"] = tuple(
        sorted(inspector.get_sequence_names(schema=schema))
    )
    snapshot["views"] = tuple(
        sorted(
            (
                view_name,
                _normalize_schema_expression(
                    inspector.get_view_definition(view_name, schema=schema),
                    schema,
                ),
            )
            for view_name in inspector.get_view_names(schema=schema)
        )
    )
    snapshot["materialized_views"] = tuple(
        sorted(inspector.get_materialized_view_names(schema=schema))
    )
    snapshot["triggers"] = tuple(
        sorted(
            (
                row.table_name,
                row.trigger_name,
                row.definition,
                row.enabled,
            )
            for row in connection.execute(
                text(
                    "SELECT relation.relname AS table_name, trg.tgname AS "
                    "trigger_name, pg_get_triggerdef(trg.oid) AS definition, "
                    "trg.tgenabled AS enabled "
                    "FROM pg_trigger AS trg "
                    "JOIN pg_class AS relation ON relation.oid = trg.tgrelid "
                    "JOIN pg_namespace AS namespace "
                    "ON namespace.oid = relation.relnamespace "
                    "WHERE namespace.nspname = :schema "
                    "AND NOT trg.tgisinternal"
                ),
                {"schema": schema},
            )
        )
    )
    snapshot["row_security"] = tuple(
        sorted(
            (
                row.relname,
                row.relrowsecurity,
                row.relforcerowsecurity,
            )
            for row in connection.execute(
                text(
                    "SELECT relation.relname, relation.relrowsecurity, "
                    "relation.relforcerowsecurity FROM pg_class AS relation "
                    "JOIN pg_namespace AS namespace "
                    "ON namespace.oid = relation.relnamespace "
                    "WHERE namespace.nspname = :schema "
                    "AND relation.relkind IN ('r', 'p') "
                    "AND (relation.relrowsecurity OR relation.relforcerowsecurity)"
                ),
                {"schema": schema},
            )
        )
    )
    return snapshot


def _execute_fixture(connection: Connection) -> None:
    source = "\n".join(
        line
        for line in LEGACY_FIXTURE.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    )
    for statement in source.split(";"):
        if statement.strip():
            connection.exec_driver_sql(statement)


def _verify_source_schema(connection: Connection, source_schema: str) -> str:
    if source_schema != LEGACY_SCHEMA:
        raise RuntimeError(
            f"Legacy adoption only supports schema {LEGACY_SCHEMA!r}; "
            f"received {source_schema!r}."
        )
    inspector = inspect(connection)
    actual_tables = frozenset(inspector.get_table_names(schema=source_schema))
    if actual_tables != LEGACY_TABLES:
        raise RuntimeError(
            "Legacy adoption requires exactly the pinned pre-0001 table set. "
            f"Missing: {sorted(LEGACY_TABLES - actual_tables)}; "
            f"unexpected: {sorted(actual_tables - LEGACY_TABLES)}."
        )
    if inspector.get_table_names(schema=ARCHIVE_SCHEMA):
        raise RuntimeError(
            f"Archive schema {ARCHIVE_SCHEMA!r} exists without a validated "
            "adoption-state record; refusing to overwrite it."
        )
    conflicting_tables = connection.execute(
        text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'manual_player_mappings' "
            "AND table_schema <> :source_schema"
        ),
        {"source_schema": source_schema},
    ).scalars().all()
    if conflicting_tables:
        raise RuntimeError(
            "Legacy adoption cannot proceed while another schema contains "
            "manual_player_mappings; migration 0002 does not schema-qualify its "
            "information_schema lookup."
        )
    conflicting_types = connection.execute(
        text(
            "SELECT typname FROM pg_type "
            "WHERE typname IN ('scoring_category', 'calc_type')"
        )
    ).scalars().all()
    if conflicting_types:
        raise RuntimeError(
            "Legacy adoption found pre-existing scoring enum type(s): "
            f"{sorted(set(conflicting_types))}; refusing to collide with migration 0003."
        )
    with connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = 'alembic_version'"
        ),
        {"schema": source_schema},
    ) as result:
        if result.first() is not None:
            raise RuntimeError(
                "Legacy adoption only accepts an unversioned pre-Alembic database."
            )

    scratch_schema = f"ffpi_legacy_check_{uuid4().hex}"
    connection.execute(CreateSchema(scratch_schema))
    try:
        connection.exec_driver_sql(
            f"SET LOCAL search_path TO {_quoted(connection, scratch_schema)}"
        )
        _execute_fixture(connection)
        expected = _schema_snapshot(connection, scratch_schema)
    finally:
        connection.execute(DropSchema(scratch_schema, cascade=True, if_exists=True))
        connection.exec_driver_sql(
            f"SET LOCAL search_path TO {_quoted(connection, source_schema)}"
        )

    actual = _schema_snapshot(connection, source_schema)
    if actual != expected:
        differing_objects = sorted(
            object_name
            for object_name in actual.keys() | expected.keys()
            if actual.get(object_name) != expected.get(object_name)
        )
        raise RuntimeError(
            "Legacy adoption source differs from the pinned fixture. "
            f"Different object(s): {differing_objects}. "
            "No source objects were changed."
        )
    return hashlib.sha256(LEGACY_FIXTURE.read_bytes()).hexdigest()


def _row_counts(connection: Connection, schema: str) -> tuple[tuple[str, int], ...]:
    return tuple(
        (
            table_name,
            connection.execute(
                text(f"SELECT count(*) FROM {_qualified(connection, schema, table_name)}")
            ).scalar_one(),
        )
        for table_name in sorted(LEGACY_TABLES)
    )


def _existing_adoption_state(connection: Connection) -> tuple[str, str] | None:
    schemas = set(inspect(connection).get_schema_names())
    if ARCHIVE_SCHEMA not in schemas:
        return None

    tables = set(inspect(connection).get_table_names(schema=ARCHIVE_SCHEMA))
    if STATE_TABLE not in tables:
        raise RuntimeError(
            f"Archive schema {ARCHIVE_SCHEMA!r} exists without adoption state; "
            "refusing to alter either schema."
        )
    state_table = _qualified(connection, ARCHIVE_SCHEMA, STATE_TABLE)
    state = connection.execute(
        text(
            f"SELECT source_fingerprint, phase FROM {state_table} "
            "ORDER BY created_at DESC LIMIT 1"
        )
    ).one_or_none()
    expected_fingerprint = hashlib.sha256(LEGACY_FIXTURE.read_bytes()).hexdigest()
    if (
        state is None
        or state.source_fingerprint != expected_fingerprint
        or state.phase not in {"prepared", "complete"}
    ):
        raise RuntimeError(
            "Existing legacy-adoption state does not match the pinned fixture; "
            "refusing automatic recovery."
        )
    return state.source_fingerprint, state.phase


def _archive_row_counts(connection: Connection) -> tuple[tuple[str, int], ...]:
    return _row_counts(connection, ARCHIVE_SCHEMA)


def _resumable_report(
    engine: Engine,
    connection: Connection,
    state: tuple[str, str],
) -> LegacyAdoptionReport:
    scoring_rules = _qualified(connection, ARCHIVE_SCHEMA, "scoring_rules")
    scoring_rule_rows = connection.execute(
        text(f"SELECT count(*) FROM {scoring_rules}")
    ).scalar_one()
    division_groups = _division_group_count(connection, ARCHIVE_SCHEMA)
    return LegacyAdoptionReport(
        database=engine.url.database,
        phase=f"resume:{state[1]}:{state[0]}",
        table_row_counts=_archive_row_counts(connection),
        scoring_rule_rows=scoring_rule_rows,
        division_groups=division_groups,
    )


def _validate_scoring_rule_mapping(connection: Connection, schema: str) -> int:
    scoring_rules = _qualified(connection, schema, "scoring_rules")
    invalid_rows = connection.execute(
        text(
            f"SELECT count(*) FROM {scoring_rules} "
            "WHERE league_id IS NULL "
            "OR category IS NULL OR BTRIM(category) = '' "
            "OR points IS NULL "
            "OR points::numeric < -99999999.99 "
            "OR points::numeric > 99999999.99 "
            "OR points::numeric <> ROUND(points::numeric, 2) "
            "OR (COALESCE(NULLIF(BTRIM(description), ''), "
            "NULLIF(BTRIM(category), '')) IS NULL) "
            "OR LENGTH(COALESCE(NULLIF(BTRIM(description), ''), "
            "NULLIF(BTRIM(category), ''))) > 100"
        )
    ).scalar_one()
    if invalid_rows:
        raise RuntimeError(
            f"Cannot map {invalid_rows} legacy scoring_rules row(s): required "
            "league, category, points, and a <=100-character event label must "
            "be present. Source data remains unchanged."
        )
    return connection.execute(
        text(f"SELECT count(*) FROM {scoring_rules}")
    ).scalar_one()


def _division_group_count(connection: Connection, schema: str) -> int:
    users = _qualified(connection, schema, "users")
    return connection.execute(
        text(
            f"SELECT count(*) FROM ("
            f"SELECT league_id, BTRIM(division) FROM {users} "
            "WHERE NULLIF(BTRIM(division), '') IS NOT NULL "
            "GROUP BY league_id, BTRIM(division)"
            ") AS legacy_division_groups"
        )
    ).scalar_one()


def inspect_legacy_database(
    engine: Engine,
    *,
    source_schema: str = LEGACY_SCHEMA,
) -> LegacyAdoptionReport:
    with engine.begin() as connection:
        existing_state = _existing_adoption_state(connection)
        if existing_state is not None:
            return _resumable_report(engine, connection, existing_state)
        source_fingerprint = _verify_source_schema(connection, source_schema)
        scoring_rule_rows = _validate_scoring_rule_mapping(connection, source_schema)
        division_groups = _division_group_count(connection, source_schema)
        row_counts = _row_counts(connection, source_schema)
    return LegacyAdoptionReport(
        database=engine.url.database,
        phase=f"validated:{source_fingerprint}",
        table_row_counts=row_counts,
        scoring_rule_rows=scoring_rule_rows,
        division_groups=division_groups,
    )


def prepare_legacy_schema(
    engine: Engine,
    *,
    source_schema: str = LEGACY_SCHEMA,
) -> LegacyAdoptionReport:
    with engine.begin() as connection:
        existing_state = _existing_adoption_state(connection)
        if existing_state is not None:
            return _resumable_report(engine, connection, existing_state)
        source_fingerprint = _verify_source_schema(connection, source_schema)
        scoring_rule_rows = _validate_scoring_rule_mapping(connection, source_schema)
        division_groups = _division_group_count(connection, source_schema)
        row_counts = _row_counts(connection, source_schema)
        connection.execute(CreateSchema(ARCHIVE_SCHEMA))

        for table_name in sorted(LEGACY_TABLES):
            source_table = _qualified(connection, source_schema, table_name)
            archive_table = _qualified(connection, ARCHIVE_SCHEMA, table_name)
            connection.exec_driver_sql(
                f"CREATE TABLE {archive_table} (LIKE {source_table} INCLUDING ALL)"
            )
            connection.exec_driver_sql(
                f"INSERT INTO {archive_table} SELECT * FROM {source_table}"
            )
            archived_rows = connection.execute(
                text(f"SELECT count(*) FROM {archive_table}")
            ).scalar_one()
            expected_rows = dict(row_counts)[table_name]
            if archived_rows != expected_rows:
                raise RuntimeError(
                    f"Archiving {table_name} copied {archived_rows} of "
                    f"{expected_rows} rows; rolling back all bridge preparation."
                )

        operations = Operations(MigrationContext.configure(connection))
        for table_name in sorted(LEGACY_TABLES):
            foreign_keys = inspect(connection).get_foreign_keys(
                table_name,
                schema=source_schema,
            )
            for index, foreign_key in enumerate(foreign_keys):
                options = foreign_key.get("options") or {}
                operations.create_foreign_key(
                    foreign_key.get("name")
                    or (
                        f"fk_{table_name}_{foreign_key['referred_table']}_{index}"
                    ),
                    table_name,
                    foreign_key["referred_table"],
                    foreign_key.get("constrained_columns") or [],
                    foreign_key.get("referred_columns") or [],
                    source_schema=ARCHIVE_SCHEMA,
                    referent_schema=ARCHIVE_SCHEMA,
                    onupdate=options.get("onupdate"),
                    ondelete=options.get("ondelete"),
                    deferrable=options.get("deferrable"),
                    initially=options.get("initially"),
                    match=options.get("match"),
                )

        connection.exec_driver_sql(
            f"CREATE TABLE {_qualified(connection, ARCHIVE_SCHEMA, STATE_TABLE)} ("
            "source_fingerprint TEXT PRIMARY KEY, "
            "phase TEXT NOT NULL, "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        connection.execute(
            text(
                f"INSERT INTO {_qualified(connection, ARCHIVE_SCHEMA, STATE_TABLE)} "
                "(source_fingerprint, phase) VALUES (:fingerprint, 'prepared')"
            ),
            {"fingerprint": source_fingerprint},
        )

        for column in (
            sa.Column("event_name", sa.String(100), nullable=True),
            sa.Column("range_min", sa.Numeric(10, 2), nullable=True),
            sa.Column("range_max", sa.Numeric(10, 2), nullable=True),
            sa.Column("point_value", sa.Numeric(10, 2), nullable=True),
            sa.Column("calculation_type", sa.String(), nullable=True),
            sa.Column("applicable_positions", sa.JSON(), nullable=True),
            sa.Column("position_ids", sa.JSON(), nullable=True),
            sa.Column("source", sa.String(32), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
        ):
            operations.add_column("scoring_rules", column)

        scoring_rules = _qualified(connection, source_schema, "scoring_rules")
        connection.execute(
            text(
                f"UPDATE {scoring_rules} SET "
                "event_name = COALESCE(NULLIF(BTRIM(description), ''), BTRIM(category)), "
                "range_min = 0, "
                "range_max = 9999.99, "
                "point_value = points::numeric, "
                "calculation_type = 'flat_bonus', "
                "applicable_positions = '[\"ALL\"]'::json, "
                "position_ids = '[]'::json, "
                "source = 'custom', "
                "is_active = TRUE"
            )
        )
        for column_name in (
            "league_id",
            "category",
            "event_name",
            "range_min",
            "range_max",
            "point_value",
            "calculation_type",
            "applicable_positions",
            "position_ids",
            "source",
            "is_active",
        ):
            operations.alter_column(
                "scoring_rules",
                column_name,
                nullable=False,
            )
        operations.drop_column("scoring_rules", "points")

        operations.create_table(
            "divisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "league_id",
                sa.Integer(),
                sa.ForeignKey("leagues.id"),
                nullable=True,
            ),
            sa.Column("season", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=True),
        )
        operations.create_index("ix_divisions_id", "divisions", ["id"])
        operations.create_index("ix_divisions_season", "divisions", ["season"])
        operations.add_column(
            "users",
            sa.Column("division_id", sa.Integer(), nullable=True),
        )
        operations.create_foreign_key(
            "users_division_id_fkey",
            "users",
            "divisions",
            ["division_id"],
            ["id"],
        )

        users = _qualified(connection, source_schema, "users")
        divisions = _qualified(connection, source_schema, "divisions")
        connection.execute(
            text(
                f"INSERT INTO {divisions} (league_id, name, order_index) "
                f"SELECT DISTINCT league_id, BTRIM(division), 0 FROM {users} "
                "WHERE NULLIF(BTRIM(division), '') IS NOT NULL"
            )
        )
        connection.execute(
            text(
                f"UPDATE {users} AS legacy_user "
                "SET division_id = division.id "
                f"FROM {divisions} AS division "
                "WHERE legacy_user.league_id IS NOT DISTINCT FROM division.league_id "
                "AND BTRIM(legacy_user.division) = division.name"
            )
        )
        operations.drop_column("users", "division")

    return LegacyAdoptionReport(
        database=engine.url.database,
        phase=f"prepared:{source_fingerprint}",
        table_row_counts=row_counts,
        scoring_rule_rows=scoring_rule_rows,
        division_groups=division_groups,
    )


def finalize_legacy_schema_adoption(engine: Engine) -> None:
    with engine.begin() as connection:
        state_table = _qualified(connection, ARCHIVE_SCHEMA, STATE_TABLE)
        state = connection.execute(
            text(
                f"SELECT source_fingerprint, phase FROM {state_table} "
                "ORDER BY created_at DESC LIMIT 1"
            )
        ).one_or_none()
        if state is None or state.phase not in {"prepared", "complete"}:
            raise RuntimeError(
                "Legacy adoption has no prepared archive state; refusing to finalize."
            )

        operations = Operations(MigrationContext.configure(connection))
        indexes = inspect(connection).get_indexes("scoring_rules", schema=LEGACY_SCHEMA)
        if any(index.get("name") == "idx_league_scoring" for index in indexes):
            operations.drop_index("idx_league_scoring", table_name="scoring_rules")
        connection.execute(text("DROP TYPE IF EXISTS calc_type"))
        connection.execute(text("DROP TYPE IF EXISTS scoring_category"))
        connection.execute(
            text(
                f"UPDATE {state_table} SET phase = 'complete' "
                "WHERE source_fingerprint = :fingerprint"
            ),
            {"fingerprint": state.source_fingerprint},
        )
