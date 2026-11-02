import os
from uuid import uuid4

from alembic import command
import pytest
import sqlalchemy as sa

from backend import apply_migrations, historical_schema_adoption as adoption
from backend.legacy_schema_bridge import _bootstrap_schema_contract, _schema_snapshot


@pytest.fixture
def adoption_copy(monkeypatch):
    url = os.getenv("FFPI_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("FFPI_TEST_POSTGRES_URL is not configured")
    name = f"ffpi_528_slice6_test_{uuid4().hex}"
    admin = sa.create_engine(url)
    engine = None
    try:
        with admin.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}" TEMPLATE template0')
        target_url = admin.url.set(database=name)
        monkeypatch.setenv(
            "DATABASE_URL", target_url.render_as_string(hide_password=False)
        )
        command.upgrade(
            apply_migrations._bootstrap_config(apply_migrations.ALEMBIC_CONFIG_PATH),
            "bootstrap_0030",
        )
        engine = sa.create_engine(target_url)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
            )
            connection.execute(
                sa.text("UPDATE alembic_version SET version_num=:version"),
                {"version": adoption.OBSERVED_REVISION},
            )
            users = sa.Table("users", sa.MetaData(), autoload_with=connection)
            connection.execute(
                users.insert(),
                [
                    {"username": "Hist_2020_0001", "is_historical_stub": False},
                    {"username": "active", "is_historical_stub": False},
                ],
            )
            snapshot = _schema_snapshot(connection, "public")
            monkeypatch.setattr(adoption, "OBSERVED_DIGEST", adoption._digest(snapshot))
        yield engine, name
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}"')
        admin.dispose()


def _version(engine):
    with engine.connect() as connection:
        return connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()


def test_guarded_copy_adoption_preserves_rows_and_converges(adoption_copy):
    engine, name = adoption_copy
    report = adoption.adopt_disposable_copy(engine, name)
    assert report["preserved_tables"] == 58
    assert report["preserved_rows"] == 2
    assert _version(engine) == adoption.TARGET_REVISION
    with engine.begin() as connection:
        actual = _schema_snapshot(connection, "public")
        actual.pop("alembic_version")
        _, expected = _bootstrap_schema_contract(connection, revision="bootstrap_0030")
        assert actual == expected
        flags = connection.execute(
            sa.text("SELECT username, is_historical_stub FROM users ORDER BY username")
        ).all()
        assert dict(flags) == {"Hist_2020_0001": True, "active": False}
    with pytest.raises(RuntimeError, match="single reviewed unknown revision"):
        adoption.adopt_disposable_copy(engine, name)


@pytest.mark.parametrize(
    "mutation",
    [
        "ALTER TABLE leagues ADD COLUMN unreviewed INTEGER",
        "ALTER TABLE users ALTER COLUMN is_historical_stub SET DEFAULT true",
        "DROP INDEX ix_draft_picks_year",
        "ALTER TABLE draft_picks DROP CONSTRAINT ck_draft_picks_source_identity",
        "CREATE TABLE unreviewed (id INTEGER)",
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(256)",
    ],
)
def test_any_unreviewed_schema_drift_blocks_adoption(adoption_copy, mutation):
    engine, name = adoption_copy
    with engine.begin() as connection:
        connection.exec_driver_sql(mutation)
    with pytest.raises(RuntimeError, match="Complete observed schema fingerprint"):
        adoption.adopt_disposable_copy(engine, name)
    assert _version(engine) == adoption.OBSERVED_REVISION


def test_row_preservation_failure_rolls_back_revision_schema_and_backfill(
    adoption_copy, monkeypatch
):
    engine, name = adoption_copy
    original = adoption._rename_bootstrap_foreign_keys

    def mutate(connection, metadata):
        original(connection, metadata)
        connection.execute(
            sa.text("UPDATE users SET username='changed' WHERE username='active'")
        )

    monkeypatch.setattr(adoption, "_rename_bootstrap_foreign_keys", mutate)
    with pytest.raises(RuntimeError, match="Original row preservation failed"):
        adoption.adopt_disposable_copy(engine, name)
    assert _version(engine) == adoption.OBSERVED_REVISION
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT username, is_historical_stub FROM users ORDER BY username")
        ).all()
        assert dict(rows) == {"Hist_2020_0001": False, "active": False}


def test_adoption_refuses_non_copy_database_before_connecting():
    engine = sa.create_engine("sqlite://")
    try:
        with pytest.raises(RuntimeError, match="explicitly named loopback"):
            adoption.adopt_disposable_copy(engine, "production")
    finally:
        engine.dispose()
