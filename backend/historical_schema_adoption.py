"""Explicit, fail-closed adoption of the preserved unknown historical revision."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json

from alembic.autogenerate import produce_migrations
from alembic.migration import MigrationContext
from alembic.operations import Operations, ops
import sqlalchemy as sa

from backend.db_config import load_backend_env_file, resolve_database_url
from backend.legacy_schema_bridge import (
    _bootstrap_schema_contract,
    _flatten_operations,
    _rename_bootstrap_foreign_keys,
    _schema_snapshot,
)

OBSERVED_REVISION = "0029_harden_historical_ingestion_models"
TARGET_REVISION = "0030_historical_ingestion"
OBSERVED_DIGEST = "2562315ddcff2a9541fcd5e85181048319ff8bfd7166862bd5bd20bb3bb127ce"
COPY_PREFIX = "ffpi_528_slice6_"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _data_digest(connection, table, *, expected_backfill=False) -> tuple[int, str]:
    hashes = []
    for row in connection.execute(sa.select(table)).mappings():
        values = dict(row)
        if (
            expected_backfill
            and table.name == "users"
            and str(values.get("username") or "").lower().startswith("hist_")
        ):
            values["is_historical_stub"] = True
        hashes.append(bytes.fromhex(_digest(values)))
    return len(hashes), hashlib.sha256(b"".join(sorted(hashes))).hexdigest()


def _sequence_state(connection) -> dict[str, tuple]:
    preparer = connection.dialect.identifier_preparer
    return {
        name: tuple(
            connection.exec_driver_sql(
                f"SELECT last_value, is_called FROM public.{preparer.quote(name)}"
            ).one()
        )
        for name in sa.inspect(connection).get_sequence_names(schema="public")
    }


def adopt_disposable_copy(engine: sa.Engine, expected_database: str) -> dict:
    url = engine.url
    if (
        url.get_backend_name() != "postgresql"
        or url.host not in {"localhost", "127.0.0.1"}
        or not expected_database.startswith(COPY_PREFIX)
        or url.database != expected_database
        or set(url.query) & {"dbname", "database", "service", "options"}
    ):
        raise RuntimeError(
            "Adoption requires an explicitly named loopback slice-6 disposable copy."
        )
    with engine.begin() as connection:
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        actual_database = connection.execute(
            sa.text("SELECT current_database()")
        ).scalar_one()
        if actual_database != expected_database:
            raise RuntimeError(
                "Connected database does not match the explicitly approved copy."
            )
        if (
            connection.execute(sa.text("SELECT current_schema()")).scalar_one()
            != "public"
        ):
            raise RuntimeError("Adoption requires the public creation schema.")
        schemas = set(sa.inspect(connection).get_schema_names()) - {
            "information_schema",
            "public",
        }
        if schemas:
            raise RuntimeError("Unexpected non-system schemas; refusing adoption.")
        tables = sa.MetaData()
        tables.reflect(connection, schema="public")
        if "public.alembic_version" not in tables.tables:
            raise RuntimeError("Missing Alembic version table.")
        for table in sorted(tables.tables.values(), key=lambda item: item.name):
            qualified = connection.dialect.identifier_preparer.format_table(table)
            connection.exec_driver_sql(
                f"LOCK TABLE {qualified} IN ACCESS EXCLUSIVE MODE"
            )
        version = tables.tables["public.alembic_version"]
        if list(connection.execute(sa.select(version.c.version_num)).scalars()) != [
            OBSERVED_REVISION
        ]:
            raise RuntimeError(
                "Copy does not report the single reviewed unknown revision."
            )
        observed = _schema_snapshot(connection, "public")
        if _digest(observed) != OBSERVED_DIGEST:
            raise RuntimeError(
                "Complete observed schema fingerprint differs; refusing adoption."
            )
        original_tables = [
            table for table in tables.tables.values() if table.name != "alembic_version"
        ]
        original_data = {
            table.name: _data_digest(connection, table, expected_backfill=True)
            for table in original_tables
        }
        sequences = _sequence_state(connection)
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "compare_server_default": True}
        )
        with Operations.context(context):
            importlib.import_module("db.migrations.0030_historical_ingestion").upgrade()
        target_metadata, expected = _bootstrap_schema_contract(connection)
        reconciliation = produce_migrations(context, target_metadata)
        operations = list(_flatten_operations(reconciliation.upgrade_ops.ops))
        if any(
            isinstance(operation, (ops.DropTableOp, ops.DropColumnOp))
            for operation in operations
        ):
            removed = [
                (operation.table_name, getattr(operation, "column_name", None))
                for operation in operations
                if isinstance(operation, (ops.DropTableOp, ops.DropColumnOp))
            ]
            raise RuntimeError(
                f"Adoption would remove existing tables or columns: {removed}; refusing."
            )
        runner = Operations(context)
        for operation in operations:
            runner.invoke(operation)
        # Alembic considers these equivalent; the complete snapshot does not.
        runner.alter_column("league_settings", "waiver_deadline", type_=sa.String())
        runner.alter_column("scoring_rules", "calculation_type", type_=sa.String())
        for column in ("created_at", "updated_at"):
            runner.alter_column(
                "scoring_rules", column, server_default=sa.text("now()")
            )
        _rename_bootstrap_foreign_keys(connection, target_metadata)
        actual = _schema_snapshot(connection, "public")
        actual.pop("alembic_version", None)
        if actual != expected:
            different = sorted(
                key
                for key in actual.keys() | expected.keys()
                if actual.get(key) != expected.get(key)
            )
            raise RuntimeError(
                f"Adoption did not converge to the complete bootstrap contract: {different}"
            )
        for table in original_tables:
            if _data_digest(connection, table) != original_data[table.name]:
                raise RuntimeError(
                    f"Original row preservation failed for {table.name}; rolling back."
                )
        if _sequence_state(connection) != sequences:
            raise RuntimeError("Original sequence state changed; rolling back.")
        result = connection.execute(
            version.update()
            .where(version.c.version_num == OBSERVED_REVISION)
            .values(version_num=TARGET_REVISION)
        )
        if result.rowcount != 1:
            raise RuntimeError("Alembic version changed during adoption; rolling back.")
        return {
            "database": expected_database,
            "revision": TARGET_REVISION,
            "schema_sha256": _digest(actual),
            "preserved_tables": len(original_data),
            "preserved_rows": sum(count for count, _ in original_data.values()),
            "preserved_sequences": len(sequences),
            "reconciliation_operations": len(operations),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable-copy", required=True)
    args = parser.parse_args()
    load_backend_env_file()
    url = resolve_database_url(
        require_explicit=True, context="historical copy adoption"
    )
    engine = sa.create_engine(url)
    try:
        print(
            json.dumps(
                adopt_disposable_copy(engine, args.disposable_copy), sort_keys=True
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
