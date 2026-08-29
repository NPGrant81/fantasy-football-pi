import pytest
import sqlalchemy as sa

from backend.services.schema_readiness_service import (
    SchemaNotReadyError,
    assert_schema_ready,
    find_schema_drift,
)


def _metadata() -> sa.MetaData:
    metadata = sa.MetaData()
    sa.Table(
        "leagues",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String),
    )
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
    )
    return metadata


def test_find_schema_drift_returns_missing_tables_and_columns():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE leagues (id INTEGER PRIMARY KEY)"))

    assert find_schema_drift(engine, _metadata()) == (
        ("users",),
        ("leagues.name",),
    )


def test_assert_schema_ready_accepts_matching_schema():
    engine = sa.create_engine("sqlite://")
    metadata = _metadata()
    metadata.create_all(engine)

    assert_schema_ready(engine, metadata)


def test_assert_schema_ready_reports_actionable_drift():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE leagues (id INTEGER PRIMARY KEY)"))

    with pytest.raises(
        SchemaNotReadyError,
        match=r"run Alembic migrations .*missing tables: users; missing columns: leagues.name",
    ):
        assert_schema_ready(engine, _metadata())

    assert find_schema_drift(engine, _metadata()) == (
        ("users",),
        ("leagues.name",),
    )
