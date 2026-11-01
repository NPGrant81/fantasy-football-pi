"""Explicit, forward-only adoption of the pinned pre-Alembic PostgreSQL schema."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import uuid4

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from alembic.autogenerate import produce_migrations
from alembic.migration import MigrationContext
from alembic.operations import Operations, ops as alembic_ops
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.schema import BLANK_SCHEMA, CreateSchema, DropSchema

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
# These empty current tables need bridge preparation for bootstrap parity.
BRIDGE_MANAGED_TABLES = frozenset(
    {
        "division_config_snapshots",
        "division_name_reports",
        "economic_ledger",
        "league_history_team_owner_map",
        "nfl_games",
        "player_aliases",
        "player_news_items",
        "player_news_links",
        "player_news_sentiment_trends",
        "playoff_matches",
        "playoff_snapshots",
        "refresh_tokens",
        "scoring_rule_change_logs",
        "scoring_rule_proposals",
        "scoring_rule_votes",
        "scoring_template_rules",
        "scoring_templates",
        "site_visits",
        "trade_assets",
        "trade_events",
        "trades",
        "unmatched_players",
        "validated_draft_results",
        "waiver_budgets",
    }
)
LEGACY_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "db"
    / "test_fixtures"
    / "pre_0001_legacy_schema.sql"
)


class LegacyScoringMapping(BaseModel):
    """Operator-reviewed semantics for one pinned legacy scoring row."""

    model_config = ConfigDict(extra="forbid")

    rule_id: int = Field(strict=True, gt=0)
    event_name: str
    calculation_type: Literal["per_unit", "flat_bonus"]
    range_min: Decimal = Field(allow_inf_nan=False, max_digits=10, decimal_places=2)
    range_max: Decimal = Field(allow_inf_nan=False, max_digits=10, decimal_places=2)
    applicable_positions: list[Literal["QB", "RB", "WR", "TE", "K", "DST", "ALL"]] = (
        Field(min_length=1)
    )

    @field_validator("event_name")
    @classmethod
    def validate_event(cls, value: str) -> str:
        from backend.services.scoring_service import STAT_KEY_ALIASES

        if value not in STAT_KEY_ALIASES or value == "fantasy_points":
            raise ValueError("event_name must be a canonical raw scoring stat key")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> LegacyScoringMapping:
        if self.range_min > self.range_max:
            raise ValueError("range_min must not exceed range_max")
        if (
            self.calculation_type == "flat_bonus"
            and self.range_min <= 0 <= self.range_max
        ):
            raise ValueError(
                "flat_bonus range must exclude zero to avoid missing-stat bonuses"
            )
        return self


@dataclass(frozen=True)
class LegacyAdoptionReport:
    database: str | None
    phase: str
    table_row_counts: tuple[tuple[str, int], ...]
    scoring_rule_rows: int
    division_groups: int
    bridge_managed_tables: tuple[str, ...]


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
                        (
                            None
                            if foreign_key.get("referred_schema") == schema
                            else foreign_key.get("referred_schema")
                        ),
                        foreign_key.get("referred_table"),
                        tuple(foreign_key.get("referred_columns") or ()),
                        tuple(sorted((foreign_key.get("options") or {}).items())),
                    )
                    for foreign_key in inspector.get_foreign_keys(
                        table_name,
                        schema=schema,
                        postgresql_ignore_search_path=True,
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
                                (column, tuple(ordering))
                                for column, ordering in (
                                    index.get("column_sorting") or {}
                                ).items()
                            )
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
        (
            row.name,
            row.data_type,
            row.start,
            row.increment,
            row.minimum,
            row.maximum,
            row.cache,
            row.cycle,
            None if row.owner_schema == schema else row.owner_schema,
            row.owner_table,
            row.owner_column,
            row.dependency_type,
        )
        for row in connection.execute(
            text(
                "SELECT seq.relname AS name, format_type(p.seqtypid, NULL) AS data_type, "
                "p.seqstart AS start, p.seqincrement AS increment, p.seqmin AS minimum, "
                "p.seqmax AS maximum, p.seqcache AS cache, p.seqcycle AS cycle, "
                "ons.nspname AS owner_schema, owner.relname AS owner_table, "
                "attr.attname AS owner_column, dep.deptype AS dependency_type "
                "FROM pg_class seq JOIN pg_namespace ns ON ns.oid = seq.relnamespace "
                "JOIN pg_sequence p ON p.seqrelid = seq.oid "
                "LEFT JOIN pg_depend dep ON dep.classid = 'pg_class'::regclass "
                "AND dep.objid = seq.oid AND dep.objsubid = 0 "
                "AND dep.refclassid = 'pg_class'::regclass AND dep.refobjsubid > 0 "
                "AND dep.deptype IN ('a', 'i') "
                "LEFT JOIN pg_class owner ON owner.oid = dep.refobjid "
                "LEFT JOIN pg_namespace ons ON ons.oid = owner.relnamespace "
                "LEFT JOIN pg_attribute attr ON attr.attrelid = owner.oid "
                "AND attr.attnum = dep.refobjsubid "
                "WHERE ns.nspname = :schema ORDER BY seq.relname"
            ),
            {"schema": schema},
        )
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
    conflicting_tables = (
        connection.execute(
            text(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = 'manual_player_mappings' "
                "AND table_schema <> :source_schema"
            ),
            {"source_schema": source_schema},
        )
        .scalars()
        .all()
    )
    if conflicting_tables:
        raise RuntimeError(
            "Legacy adoption cannot proceed while another schema contains "
            "manual_player_mappings; migration 0002 does not schema-qualify its "
            "information_schema lookup."
        )
    conflicting_types = (
        connection.execute(
            text(
                "SELECT typname FROM pg_type "
                "WHERE typname IN ('scoring_category', 'calc_type')"
            )
        )
        .scalars()
        .all()
    )
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
                text(
                    f"SELECT count(*) FROM {_qualified(connection, schema, table_name)}"
                )
            ).scalar_one(),
        )
        for table_name in sorted(LEGACY_TABLES)
    )


def _create_bridge_managed_tables(connection: Connection) -> None:
    from backend.models import Base

    missing_metadata = BRIDGE_MANAGED_TABLES - set(Base.metadata.tables)
    if missing_metadata:
        raise RuntimeError(
            "The bridge-managed table list is absent from ORM metadata: "
            f"{sorted(missing_metadata)}."
        )
    Base.metadata.create_all(
        bind=connection,
        tables=[
            Base.metadata.tables[table_name]
            for table_name in sorted(BRIDGE_MANAGED_TABLES)
        ],
        checkfirst=True,
    )


def _flatten_operations(
    operations: Iterable[alembic_ops.MigrateOperation],
) -> Iterator[alembic_ops.MigrateOperation]:
    for operation in operations:
        if isinstance(operation, alembic_ops.ModifyTableOps):
            yield from _flatten_operations(operation.ops)
        else:
            yield operation


def _archive_reconciliation_data(
    connection: Connection,
    table_names: set[str],
) -> None:
    _lock_source_tables(connection, LEGACY_SCHEMA, table_names)
    inspector = inspect(connection)
    archive_tables = set(inspector.get_table_names(schema=ARCHIVE_SCHEMA))
    for table_name in sorted(table_names):
        source_table = _qualified(connection, LEGACY_SCHEMA, table_name)
        archive_table_name = f"reconcile_{table_name}"
        archive_table = _qualified(connection, ARCHIVE_SCHEMA, archive_table_name)
        source_rows = connection.execute(
            text(f"SELECT count(*) FROM {source_table}")
        ).scalar_one()
        if not source_rows:
            continue
        if archive_table_name not in archive_tables:
            connection.exec_driver_sql(
                f"CREATE TABLE {archive_table} " f"(LIKE {source_table} INCLUDING ALL)"
            )
            connection.exec_driver_sql(
                f"INSERT INTO {archive_table} SELECT * FROM {source_table}"
            )
        archived_rows = connection.execute(
            text(f"SELECT count(*) FROM {archive_table}")
        ).scalar_one()
        source_alias = _quoted(connection, "source_row")
        archive_alias = _quoted(connection, "archive_row")
        rows_differ = connection.execute(
            text(
                "SELECT EXISTS ("
                f"(SELECT to_jsonb({source_alias}) FROM {source_table} "
                f"AS {source_alias} EXCEPT "
                f"SELECT to_jsonb({archive_alias}) FROM {archive_table} "
                f"AS {archive_alias}) UNION ALL "
                f"(SELECT to_jsonb({archive_alias}) FROM {archive_table} "
                f"AS {archive_alias} EXCEPT "
                f"SELECT to_jsonb({source_alias}) FROM {source_table} "
                f"AS {source_alias})"
                ")"
            )
        ).scalar_one()
        if archived_rows != source_rows or rows_differ:
            raise RuntimeError(
                f"Schema reconciliation archive for {table_name} does not "
                "exactly match its source; refusing to remove or alter data."
            )


def _bootstrap_schema_contract(
    connection: Connection,
) -> tuple[sa.MetaData, dict[str, object]]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    bootstrap_directory = Path(__file__).resolve().parents[1] / "db" / "bootstrap"
    config = Config()
    config.set_main_option("script_location", str(bootstrap_directory))
    config.set_main_option(
        "version_locations",
        str(bootstrap_directory / "versions"),
    )
    script = ScriptDirectory.from_config(config)
    if len(script.get_heads()) != 1:
        raise RuntimeError(
            "Bootstrap schema contract must have exactly one revision head."
        )

    contract_schema = f"ffpi_bootstrap_contract_{uuid4().hex}"
    with connection.begin_nested():
        connection.execute(CreateSchema(contract_schema))
        connection.exec_driver_sql(
            f"SET LOCAL search_path TO {_quoted(connection, contract_schema)}"
        )
        for revision in reversed(list(script.walk_revisions())):
            with Operations.context(MigrationContext.configure(connection)):
                revision.module.upgrade()

        contract_snapshot = _schema_snapshot(connection, contract_schema)
        reflected_metadata = sa.MetaData()
        reflected_metadata.reflect(bind=connection, schema=contract_schema)
        target_metadata = sa.MetaData()
        for source_table in reflected_metadata.tables.values():
            target_table = source_table.to_metadata(
                target_metadata,
                schema=None,
                referred_schema_fn=(
                    lambda table, to_schema, constraint, referred_schema: (
                        BLANK_SCHEMA if referred_schema == contract_schema else None
                    )
                ),
            )
            for constraint in list(target_table.foreign_key_constraints):
                target_table.constraints.remove(constraint)
            for column in target_table.columns:
                column.foreign_keys.clear()
            for constraint in source_table.foreign_key_constraints:
                target_table.append_constraint(
                    sa.ForeignKeyConstraint(
                        [element.parent.name for element in constraint.elements],
                        [
                            f"{element.column.table.name}.{element.column.name}"
                            for element in constraint.elements
                        ],
                        name=constraint.name,
                        onupdate=constraint.onupdate,
                        ondelete=constraint.ondelete,
                        deferrable=constraint.deferrable,
                        initially=constraint.initially,
                        match=constraint.match,
                    )
                )
            for column in target_table.columns:
                if column.server_default is None:
                    continue
                expression = str(column.server_default.arg)
                normalized = _normalize_schema_expression(
                    expression,
                    contract_schema,
                )
                if normalized != expression:
                    column.server_default = sa.DefaultClause(sa.text(str(normalized)))

        connection.execute(DropSchema(contract_schema, cascade=True, if_exists=True))
        connection.exec_driver_sql(
            f"SET LOCAL search_path TO {_quoted(connection, LEGACY_SCHEMA)}"
        )

    return target_metadata, contract_snapshot


def _foreign_key_signature(
    constrained_columns: Iterable[str],
    referred_table: str | None,
    referred_columns: Iterable[str],
) -> tuple[tuple[str, ...], str | None, tuple[str, ...]]:
    return (
        tuple(constrained_columns),
        referred_table,
        tuple(referred_columns),
    )


def _rename_bootstrap_foreign_keys(
    connection: Connection,
    metadata: sa.MetaData,
) -> None:
    for table in metadata.tables.values():
        expected = {
            _foreign_key_signature(
                [element.parent.name for element in constraint.elements],
                constraint.elements[0].column.table.name,
                [element.column.name for element in constraint.elements],
            ): constraint.name
            for constraint in table.foreign_key_constraints
            if constraint.name and constraint.elements
        }
        for signature, expected_name in expected.items():
            actual_foreign_keys = inspect(connection).get_foreign_keys(
                table.name,
                schema=LEGACY_SCHEMA,
            )
            matches = [
                foreign_key
                for foreign_key in actual_foreign_keys
                if _foreign_key_signature(
                    foreign_key.get("constrained_columns") or (),
                    foreign_key.get("referred_table"),
                    foreign_key.get("referred_columns") or (),
                )
                == signature
            ]
            if len(matches) != 1 or matches[0].get("name") == expected_name:
                continue
            existing_name = matches[0].get("name")
            if not existing_name or any(
                foreign_key.get("name") == expected_name
                for foreign_key in actual_foreign_keys
            ):
                raise RuntimeError(
                    f"Cannot safely rename foreign key on {table.name} to "
                    f"{expected_name!r}; the bootstrap constraint name is "
                    "missing or already in use."
                )
            connection.exec_driver_sql(
                f"ALTER TABLE {_qualified(connection, LEGACY_SCHEMA, table.name)} "
                f"RENAME CONSTRAINT {_quoted(connection, existing_name)} "
                f"TO {_quoted(connection, expected_name)}"
            )


def reconcile_adopted_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        _require_public_creation_schema(connection)
        target_metadata, bootstrap_snapshot = _bootstrap_schema_contract(connection)
        migration_context = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
            },
        )
        migration_script = produce_migrations(
            migration_context,
            target_metadata,
        )
        operations = list(_flatten_operations(migration_script.upgrade_ops.ops))
        tables_to_drop = [
            operation.table_name
            for operation in operations
            if isinstance(operation, alembic_ops.DropTableOp)
        ]
        if tables_to_drop:
            raise RuntimeError(
                "Schema reconciliation found tables absent from the bootstrap "
                f"metadata: {sorted(tables_to_drop)}. Refusing to drop tables."
            )
        tables_with_dropped_columns = {
            operation.table_name
            for operation in operations
            if isinstance(operation, alembic_ops.DropColumnOp)
        }
        _archive_reconciliation_data(connection, tables_with_dropped_columns)
        migration_operations = Operations(migration_context)
        for operation in operations:
            migration_operations.invoke(operation)

        _rename_bootstrap_foreign_keys(connection, target_metadata)
        remaining_script = produce_migrations(
            migration_context,
            target_metadata,
        )
        if not remaining_script.upgrade_ops.is_empty():
            remaining_operations = list(
                _flatten_operations(remaining_script.upgrade_ops.ops)
            )
            raise RuntimeError(
                "Schema reconciliation did not converge to the bootstrap "
                "schema contract. "
                f"Remaining operations: {remaining_operations!r}."
            )

        actual_snapshot = _schema_snapshot(connection, LEGACY_SCHEMA)
        actual_snapshot.pop("alembic_version", None)
        if actual_snapshot != bootstrap_snapshot:
            differing_objects = sorted(
                object_name
                for object_name in actual_snapshot.keys() | bootstrap_snapshot.keys()
                if actual_snapshot.get(object_name)
                != bootstrap_snapshot.get(object_name)
            )
            raise RuntimeError(
                "Schema reconciliation did not exactly match the bootstrap "
                f"schema contract. Different object(s): {differing_objects}."
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
        bridge_managed_tables=tuple(sorted(BRIDGE_MANAGED_TABLES)),
    )


def _lock_source_tables(
    connection: Connection, schema: str, table_names: Iterable[str]
) -> None:
    tables = sorted(table_names)
    if tables:
        connection.exec_driver_sql(
            "LOCK TABLE "
            + ", ".join(_qualified(connection, schema, table) for table in tables)
            + " IN ACCESS EXCLUSIVE MODE"
        )


def _require_public_creation_schema(connection: Connection) -> None:
    schema = connection.execute(text("SELECT current_schema()")).scalar_one()
    if schema != LEGACY_SCHEMA:
        raise RuntimeError(
            "Legacy adoption requires public as the effective creation schema "
            f"on every connection; found {schema!r}. Set search_path to public "
            "before preflight or retry. No adoption changes were made."
        )


def _validate_lineup_fields(connection: Connection, schema: str) -> None:
    table = _qualified(connection, schema, "lineup_submissions")
    invalid_rows = connection.execute(
        text(f"SELECT count(*) FROM {table} WHERE season IS NULL OR week IS NULL")
    ).scalar_one()
    if invalid_rows:
        raise RuntimeError(
            f"Cannot adopt {invalid_rows} lineup_submissions row(s) with NULL "
            "season or week. Source data remains unchanged."
        )


def _validate_scoring_rule_mapping(
    connection: Connection,
    schema: str,
    scoring_mappings: tuple[LegacyScoringMapping, ...],
) -> int:
    scoring_rules = _qualified(connection, schema, "scoring_rules")
    invalid_rows = connection.execute(
        text(
            f"SELECT count(*) FROM {scoring_rules} "
            "WHERE league_id IS NULL "
            "OR category IS NULL OR BTRIM(category) = '' "
            "OR points IS NULL "
            "OR points::numeric < -99999999.99 "
            "OR points::numeric > 99999999.99 "
            "OR points::numeric <> ROUND(points::numeric, 2)"
        )
    ).scalar_one()
    if invalid_rows:
        raise RuntimeError(
            f"Cannot map {invalid_rows} legacy scoring_rules row(s): required "
            "league, category, and losslessly representable points must "
            "be present. Source data remains unchanged."
        )
    rows = connection.execute(text(f"SELECT id, category FROM {scoring_rules}")).all()
    mapping_ids = [mapping.rule_id for mapping in scoring_mappings]
    if len(mapping_ids) != len(set(mapping_ids)) or set(mapping_ids) != {
        row.id for row in rows
    }:
        raise RuntimeError(
            "Cannot map legacy scoring_rules: provide exactly one explicit "
            "validated scoring mapping per source rule ID, with no extra IDs."
        )
    from backend.services.scoring_service import STAT_KEY_ALIASES

    mappings_by_id = {mapping.rule_id: mapping for mapping in scoring_mappings}
    stat_keys = {
        alias: event for event, aliases in STAT_KEY_ALIASES.items() for alias in aliases
    }
    for row in rows:
        category = row.category.lower().strip().replace(" ", "_")
        event = mappings_by_id[row.id].event_name
        if category in stat_keys and stat_keys[category] != event:
            raise RuntimeError(
                f"Cannot map legacy scoring_rules row {row.id}: category "
                f"{row.category!r} conflicts with reviewed event {event!r}."
            )
    return len(rows)


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
    scoring_mappings: tuple[LegacyScoringMapping, ...] = (),
) -> LegacyAdoptionReport:
    with engine.begin() as connection:
        _require_public_creation_schema(connection)
        existing_state = _existing_adoption_state(connection)
        if existing_state is not None:
            return _resumable_report(engine, connection, existing_state)
        source_fingerprint = _verify_source_schema(connection, source_schema)
        scoring_rule_rows = _validate_scoring_rule_mapping(
            connection, source_schema, scoring_mappings
        )
        _validate_lineup_fields(connection, source_schema)
        division_groups = _division_group_count(connection, source_schema)
        row_counts = _row_counts(connection, source_schema)
    return LegacyAdoptionReport(
        database=engine.url.database,
        phase=f"validated:{source_fingerprint}",
        table_row_counts=row_counts,
        scoring_rule_rows=scoring_rule_rows,
        division_groups=division_groups,
        bridge_managed_tables=tuple(sorted(BRIDGE_MANAGED_TABLES)),
    )


def prepare_legacy_schema(
    engine: Engine,
    *,
    source_schema: str = LEGACY_SCHEMA,
    scoring_mappings: tuple[LegacyScoringMapping, ...] = (),
) -> LegacyAdoptionReport:
    with engine.begin() as connection:
        _require_public_creation_schema(connection)
        existing_state = _existing_adoption_state(connection)
        if existing_state is not None:
            return _resumable_report(engine, connection, existing_state)
        _lock_source_tables(connection, source_schema, LEGACY_TABLES)
        source_fingerprint = _verify_source_schema(connection, source_schema)
        scoring_rule_rows = _validate_scoring_rule_mapping(
            connection, source_schema, scoring_mappings
        )
        _validate_lineup_fields(connection, source_schema)
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
                    or (f"fk_{table_name}_{foreign_key['referred_table']}_{index}"),
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
        for mapping in scoring_mappings:
            connection.execute(
                text(
                    f"UPDATE {scoring_rules} SET "
                    "event_name = :event_name, range_min = :range_min, "
                    "range_max = :range_max, point_value = points::numeric, "
                    "calculation_type = :calculation_type, "
                    "applicable_positions = CAST(:positions AS json), "
                    "position_ids = '[]'::json, source = 'custom', is_active = TRUE "
                    "WHERE id = :rule_id"
                ),
                {
                    "rule_id": mapping.rule_id,
                    "event_name": mapping.event_name,
                    "range_min": mapping.range_min,
                    "range_max": mapping.range_max,
                    "calculation_type": mapping.calculation_type,
                    "positions": json.dumps(mapping.applicable_positions),
                },
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
        _create_bridge_managed_tables(connection)

    return LegacyAdoptionReport(
        database=engine.url.database,
        phase=f"prepared:{source_fingerprint}",
        table_row_counts=row_counts,
        scoring_rule_rows=scoring_rule_rows,
        division_groups=division_groups,
        bridge_managed_tables=tuple(sorted(BRIDGE_MANAGED_TABLES)),
    )


def finalize_legacy_schema_adoption(engine: Engine) -> None:
    with engine.begin() as connection:
        _require_public_creation_schema(connection)
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
