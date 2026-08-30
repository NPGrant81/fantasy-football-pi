import ast
import importlib
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from backend import apply_migrations as migration_runner


def test_ffpi_application_tables_match_orm_metadata():
    importlib.import_module("backend.models")
    importlib.import_module("backend.models_draft_value")
    database = importlib.import_module("backend.database")

    assert migration_runner.FFPI_APPLICATION_TABLES == frozenset(
        database.Base.metadata.tables
    )


def test_ffpi_application_tables_match_bootstrap_schema():
    bootstrap_revision = (
        migration_runner.BOOTSTRAP_SCRIPT_PATH
        / "versions"
        / "0001_create_schema_at_0028.py"
    )
    syntax_tree = ast.parse(bootstrap_revision.read_text(encoding="utf-8"))
    bootstrap_tables = {
        node.args[0].value
        for node in ast.walk(syntax_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_table"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }

    assert migration_runner.FFPI_APPLICATION_TABLES == frozenset(bootstrap_tables)


@pytest.mark.parametrize(
    "table_names",
    [
        [],
        ["monitoring_events"],
        ["alembic_version", "monitoring_events"],
    ],
)
def test_database_is_empty_ignores_unrelated_tables(monkeypatch, table_names):
    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement):
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    class FakeInspector:
        def get_table_names(self):
            return table_names

    monkeypatch.setattr(
        migration_runner,
        "inspect",
        lambda _engine: FakeInspector(),
    )

    assert migration_runner._database_is_empty(FakeEngine(), frozenset()) is True


@pytest.mark.parametrize("ffpi_table", sorted(migration_runner.FFPI_APPLICATION_TABLES))
def test_database_is_empty_rejects_any_partial_ffpi_schema(
    monkeypatch,
    ffpi_table,
):
    class FakeInspector:
        def get_table_names(self):
            return ["monitoring_events", ffpi_table]

    monkeypatch.setattr(
        migration_runner,
        "inspect",
        lambda _engine: FakeInspector(),
    )

    with pytest.raises(RuntimeError, match="partial FFPI schema"):
        migration_runner._database_is_empty(object(), frozenset())


def test_database_is_empty_rejects_foreign_alembic_history(
    monkeypatch,
):
    class FakeScalars:
        def all(self):
            return ["foreign_revision"]

    class FakeResult:
        def scalars(self):
            return FakeScalars()

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement):
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    class FakeInspector:
        def get_table_names(self):
            return ["alembic_version", "monitoring_events"]

    monkeypatch.setattr(
        migration_runner,
        "inspect",
        lambda _engine: FakeInspector(),
    )

    with pytest.raises(RuntimeError, match="unknown Alembic revision"):
        migration_runner._database_is_empty(FakeEngine(), frozenset({"ffpi_revision"}))


def test_database_is_empty_recognizes_established_ffpi_database(monkeypatch):
    class FakeScalars:
        def all(self):
            return ["ffpi_revision"]

    class FakeResult:
        def scalars(self):
            return FakeScalars()

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement):
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    class FakeInspector:
        def get_table_names(self):
            return ["alembic_version", "users"]

    monkeypatch.setattr(
        migration_runner,
        "inspect",
        lambda _engine: FakeInspector(),
    )

    assert (
        migration_runner._database_is_empty(
            FakeEngine(),
            frozenset({"ffpi_revision"}),
        )
        is False
    )


def test_database_is_empty_rejects_known_history_without_ffpi_tables(monkeypatch):
    class FakeScalars:
        def all(self):
            return ["ffpi_revision"]

    class FakeResult:
        def scalars(self):
            return FakeScalars()

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement):
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    class FakeInspector:
        def get_table_names(self):
            return ["alembic_version", "monitoring_events"]

    monkeypatch.setattr(
        migration_runner,
        "inspect",
        lambda _engine: FakeInspector(),
    )

    with pytest.raises(RuntimeError, match="history but no recognized FFPI tables"):
        migration_runner._database_is_empty(
            FakeEngine(),
            frozenset({"ffpi_revision"}),
        )


@pytest.mark.parametrize(
    ("database_state", "expected_empty", "error_pattern"),
    [
        ("empty", True, None),
        ("unrelated", True, None),
        ("partial", None, "partial FFPI schema"),
        ("established", False, None),
        ("foreign_history", None, "unknown Alembic revision"),
    ],
)
def test_database_classification_with_postgresql(
    database_state,
    expected_empty,
    error_pattern,
):
    database_url = os.getenv("FFPI_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("FFPI_TEST_POSTGRES_URL is not configured")

    schema_name = f"ffpi_issue507_{uuid4().hex}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    test_engine = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema_name))

        test_engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema_name}"},
        )
        metadata = MetaData()
        if database_state == "unrelated":
            Table("monitoring_events", metadata, Column("id", Integer))
        elif database_state == "partial":
            Table("scoring_rules", metadata, Column("id", Integer))
        elif database_state == "established":
            Table("users", metadata, Column("id", Integer))
            Table(
                "alembic_version",
                metadata,
                Column("version_num", String(255), nullable=False),
            )
        elif database_state == "foreign_history":
            Table(
                "alembic_version",
                metadata,
                Column("version_num", String(255), nullable=False),
            )
        metadata.create_all(test_engine)

        if database_state in {"established", "foreign_history"}:
            revision = (
                "ffpi_revision"
                if database_state == "established"
                else "foreign_revision"
            )
            with test_engine.begin() as connection:
                connection.execute(
                    metadata.tables["alembic_version"].insert().values(
                        version_num=revision
                    )
                )

        if error_pattern:
            with pytest.raises(RuntimeError, match=error_pattern):
                migration_runner._database_is_empty(
                    test_engine,
                    frozenset({"ffpi_revision"}),
                )
        else:
            assert (
                migration_runner._database_is_empty(
                    test_engine,
                    frozenset({"ffpi_revision"}),
                )
                is expected_empty
            )
    finally:
        if test_engine is not None:
            test_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema_name, cascade=True, if_exists=True))
        admin_engine.dispose()


def test_apply_migrations_upgrades_all_heads_for_established_database(monkeypatch, tmp_path):
    config_path = tmp_path / "alembic.ini"
    config_path.write_text("[alembic]\nscript_location = db\n", encoding="ascii")
    calls = []

    class FakeConfig:
        def __init__(self, path):
            calls.append(("config", path))

    class FakeEngine:
        def dispose(self):
            calls.append(("dispose",))

    monkeypatch.setattr(migration_runner, "load_backend_env_file", lambda: None)
    monkeypatch.setattr(
        migration_runner,
        "resolve_database_url",
        lambda **kwargs: calls.append(("resolve", kwargs)) or "postgresql://test/db",
    )
    monkeypatch.setattr(
        migration_runner,
        "create_engine",
        lambda url, **kwargs: calls.append(("engine", url, kwargs)) or FakeEngine(),
    )
    monkeypatch.setattr(migration_runner, "Config", FakeConfig)
    monkeypatch.setattr(
        migration_runner,
        "_database_is_empty",
        lambda _engine, _revisions: False,
    )
    monkeypatch.setattr(
        migration_runner,
        "_known_revisions",
        lambda _config: frozenset({"ffpi_revision"}),
    )
    monkeypatch.setattr(
        migration_runner.command,
        "upgrade",
        lambda config, revision: calls.append(("upgrade", config, revision)),
    )

    migration_runner.apply_migrations(config_path)

    resolve_call = next(call for call in calls if call[0] == "resolve")
    assert resolve_call[1]["require_explicit"] is True
    upgrades = [call for call in calls if call[0] == "upgrade"]
    assert upgrades[-1][2] == "heads"
    assert calls[-1] == ("dispose",)


def test_apply_migrations_bootstraps_empty_database(monkeypatch, tmp_path):
    config_path = tmp_path / "alembic.ini"
    config_path.write_text("[alembic]\n", encoding="ascii")
    calls = []

    class FakeConfig:
        def __init__(self, path):
            self.path = path
            calls.append(("config", path))

        def set_main_option(self, name, value):
            calls.append(("option", name, value))

    class FakeEngine:
        def dispose(self):
            calls.append(("dispose",))

    monkeypatch.setattr(migration_runner, "load_backend_env_file", lambda: None)
    monkeypatch.setattr(
        migration_runner,
        "resolve_database_url",
        lambda **kwargs: "postgresql://test/db",
    )
    monkeypatch.setattr(
        migration_runner,
        "create_engine",
        lambda *_args, **_kwargs: FakeEngine(),
    )
    monkeypatch.setattr(migration_runner, "Config", FakeConfig)
    monkeypatch.setattr(
        migration_runner,
        "_database_is_empty",
        lambda _engine, _revisions: True,
    )
    monkeypatch.setattr(
        migration_runner,
        "_known_revisions",
        lambda _config: frozenset({"ffpi_revision"}),
    )
    monkeypatch.setattr(
        migration_runner.command,
        "upgrade",
        lambda config, revision: calls.append(("upgrade", config, revision)),
    )
    monkeypatch.setattr(
        migration_runner.command,
        "stamp",
        lambda config, revision, purge: calls.append(
            ("stamp", config, revision, purge)
        ),
    )

    migration_runner.apply_migrations(config_path)

    operations = [call[0] for call in calls]
    assert operations.count("upgrade") == 2
    assert any(
        call[0] == "stamp"
        and call[2] == migration_runner.BOOTSTRAP_MAIN_REVISION
        and call[3] is True
        for call in calls
    )
    upgrades = [call for call in calls if call[0] == "upgrade"]
    assert [call[2] for call in upgrades] == ["head", "heads"]
    assert calls[-1] == ("dispose",)


def test_apply_migrations_rejects_partial_schema_before_commands(
    monkeypatch,
    tmp_path,
):
    config_path = tmp_path / "alembic.ini"
    config_path.write_text("[alembic]\n", encoding="ascii")
    calls = []

    class FakeEngine:
        def dispose(self):
            calls.append(("dispose",))

    class FakeInspector:
        def get_table_names(self):
            return ["monitoring_events", "scoring_rules"]

    monkeypatch.setattr(migration_runner, "load_backend_env_file", lambda: None)
    monkeypatch.setattr(
        migration_runner,
        "resolve_database_url",
        lambda **_kwargs: "postgresql://test/db",
    )
    monkeypatch.setattr(
        migration_runner,
        "create_engine",
        lambda *_args, **_kwargs: FakeEngine(),
    )
    monkeypatch.setattr(
        migration_runner,
        "inspect",
        lambda _engine: FakeInspector(),
    )
    monkeypatch.setattr(migration_runner, "Config", lambda _path: object())
    monkeypatch.setattr(
        migration_runner,
        "_known_revisions",
        lambda _config: frozenset({"ffpi_revision"}),
    )
    monkeypatch.setattr(
        migration_runner.command,
        "upgrade",
        lambda *_args, **_kwargs: calls.append(("upgrade",)),
    )
    monkeypatch.setattr(
        migration_runner.command,
        "stamp",
        lambda *_args, **_kwargs: calls.append(("stamp",)),
    )

    with pytest.raises(RuntimeError, match="partial FFPI schema"):
        migration_runner.apply_migrations(config_path)

    assert calls == [("dispose",)]


def test_default_alembic_config_exists():
    assert isinstance(migration_runner.ALEMBIC_CONFIG_PATH, Path)
    assert migration_runner.ALEMBIC_CONFIG_PATH.is_file()
