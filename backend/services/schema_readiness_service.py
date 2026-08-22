from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import MetaData


class SchemaNotReadyError(RuntimeError):
    """Raised when the database schema does not satisfy ORM metadata."""


def find_schema_drift(
    engine: Engine,
    metadata: MetaData,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    inspector = inspect(engine)
    database_tables = set(inspector.get_table_names())
    required_tables = set(metadata.tables)
    missing_tables = tuple(sorted(required_tables - database_tables))

    missing_columns: list[str] = []
    for table_name in sorted(required_tables & database_tables):
        database_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        for column_name in sorted(metadata.tables[table_name].columns.keys()):
            if column_name not in database_columns:
                missing_columns.append(f"{table_name}.{column_name}")

    return missing_tables, tuple(missing_columns)


def assert_schema_ready(engine: Engine, metadata: MetaData) -> None:
    missing_tables, missing_columns = find_schema_drift(engine, metadata)
    if not missing_tables and not missing_columns:
        return

    details: list[str] = []
    if missing_tables:
        details.append(f"missing tables: {_format_items(missing_tables)}")
    if missing_columns:
        details.append(f"missing columns: {_format_items(missing_columns)}")

    raise SchemaNotReadyError(
        "Database schema is not ready; run Alembic migrations (" + "; ".join(details) + ")"
    )


def _format_items(items: Iterable[str]) -> str:
    return ", ".join(items)
