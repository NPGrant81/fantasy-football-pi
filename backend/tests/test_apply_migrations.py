import ast
import importlib
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from backend import apply_migrations as migration_runner


def _migration_schema_snapshot(engine):
    inspector = inspect(engine)
    snapshot = {}
    for table_name in sorted(
        name for name in inspector.get_table_names() if name != "alembic_version"
    ):
        columns = tuple(
            sorted(
                (
                    column["name"],
                    column["type"].compile(dialect=engine.dialect),
                    column["nullable"],
                    column.get("default"),
                )
                for column in inspector.get_columns(table_name)
            )
        )
        primary_key = inspector.get_pk_constraint(table_name)
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
                    for foreign_key in inspector.get_foreign_keys(table_name)
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
                    for constraint in inspector.get_unique_constraints(table_name)
                ],
                key=repr,
            )
        )
        check_constraints = tuple(
            sorted(
                [
                    (constraint.get("name"), constraint.get("sqltext"))
                    for constraint in inspector.get_check_constraints(table_name)
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
                        tuple(index.get("expressions") or ()),
                        tuple(
                            sorted(
                                (key, str(value))
                                for key, value in (
                                    index.get("dialect_options") or {}
                                ).items()
                            )
                        ),
                    )
                    for index in inspector.get_indexes(table_name)
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
    with engine.connect() as connection:
        snapshot["sequences"] = tuple(
            tuple(row)
            for row in connection.execute(
                text(
                    "SELECT sequence.relname, format_type(properties.seqtypid, NULL), "
                    "properties.seqstart, properties.seqincrement, properties.seqmin, "
                    "properties.seqmax, properties.seqcache, properties.seqcycle, "
                    "owner_namespace.nspname, owner_table.relname, owner_column.attname, "
                    "dependency.deptype "
                    "FROM pg_class AS sequence "
                    "JOIN pg_namespace AS namespace ON namespace.oid = sequence.relnamespace "
                    "JOIN pg_sequence AS properties ON properties.seqrelid = sequence.oid "
                    "LEFT JOIN pg_depend AS dependency "
                    "ON dependency.classid = 'pg_class'::regclass "
                    "AND dependency.objid = sequence.oid AND dependency.objsubid = 0 "
                    "AND dependency.refclassid = 'pg_class'::regclass "
                    "AND dependency.refobjsubid > 0 AND dependency.deptype IN ('a', 'i') "
                    "LEFT JOIN pg_class AS owner_table ON owner_table.oid = dependency.refobjid "
                    "LEFT JOIN pg_namespace AS owner_namespace "
                    "ON owner_namespace.oid = owner_table.relnamespace "
                    "LEFT JOIN pg_attribute AS owner_column "
                    "ON owner_column.attrelid = owner_table.oid "
                    "AND owner_column.attnum = dependency.refobjsubid "
                    "WHERE namespace.nspname = current_schema() "
                    "ORDER BY sequence.relname, owner_namespace.nspname, "
                    "owner_table.relname, owner_column.attname"
                )
            )
        )
    return snapshot


@pytest.fixture
def schema_snapshot_engine():
    database_url = os.getenv("FFPI_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("FFPI_TEST_POSTGRES_URL is not configured")

    schema_name = f"ffpi_snapshot_{uuid4().hex}"
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
        with test_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE snapshot_probe (id SERIAL PRIMARY KEY, payload JSON)"
            )
            connection.exec_driver_sql(
                "CREATE INDEX snapshot_expression ON snapshot_probe "
                "USING gin ((payload::jsonb))"
            )
        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema_name, cascade=True, if_exists=True))
        admin_engine.dispose()


def test_schema_snapshot_detects_changed_index_expression(schema_snapshot_engine):
    engine = schema_snapshot_engine
    baseline = _migration_schema_snapshot(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX snapshot_expression")
        connection.exec_driver_sql(
            "CREATE INDEX snapshot_expression ON snapshot_probe "
            "USING gin ((payload::jsonb -> 'stats'))"
        )
    changed = _migration_schema_snapshot(engine)
    assert changed["snapshot_probe"]["indexes"] != baseline["snapshot_probe"]["indexes"]
    assert changed["sequences"] == baseline["sequences"]


@pytest.mark.parametrize(
    "alteration",
    [
        "INCREMENT BY -1",
        "MINVALUE 0",
        "MAXVALUE 100000",
        "START WITH 2",
        "CACHE 10",
        "CYCLE",
        "AS BIGINT",
        "OWNED BY NONE",
        "OWNED BY snapshot_probe.payload",
    ],
)
def test_schema_snapshot_detects_sequence_structure_changes(
    schema_snapshot_engine, alteration
):
    engine = schema_snapshot_engine
    baseline = _migration_schema_snapshot(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"ALTER SEQUENCE snapshot_probe_id_seq {alteration}"
        )
    assert _migration_schema_snapshot(engine)["sequences"] != baseline["sequences"]


def test_schema_snapshot_ignores_sequence_runtime_state(schema_snapshot_engine):
    engine = schema_snapshot_engine
    baseline = _migration_schema_snapshot(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO snapshot_probe (payload) VALUES ('{}')"
        )
        connection.exec_driver_sql(
            "SELECT setval('snapshot_probe_id_seq', 50, true)"
        )
    assert _migration_schema_snapshot(engine) == baseline


def _migration_url_for_database(database_url, database_name):
    url = make_url(database_url)
    return url.set(database=database_name).render_as_string(hide_password=False)


def _alembic_versions(engine):
    with engine.connect() as connection:
        return frozenset(
            connection.execute(text("SELECT version_num FROM alembic_version"))
            .scalars()
            .all()
        )


def _alembic_version_column_length(engine):
    version_column = next(
        column
        for column in inspect(engine).get_columns("alembic_version")
        if column["name"] == "version_num"
    )
    return version_column["type"].length


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


@pytest.mark.parametrize(
    ("ffpi_tables", "known_revisions", "head_revisions"),
    [
        (
            migration_runner.FFPI_APPLICATION_TABLES,
            frozenset({"ffpi_revision"}),
            frozenset({"ffpi_revision"}),
        ),
        (
            frozenset({"users"}),
            frozenset({"ffpi_revision", "current_revision"}),
            frozenset({"current_revision"}),
        ),
    ],
)
def test_database_is_empty_recognizes_established_ffpi_database(
    monkeypatch,
    ffpi_tables,
    known_revisions,
    head_revisions,
):
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
            return ["alembic_version", *ffpi_tables]

    monkeypatch.setattr(
        migration_runner,
        "inspect",
        lambda _engine: FakeInspector(),
    )

    assert (
        migration_runner._database_is_empty(
            FakeEngine(),
            known_revisions,
            head_revisions,
        )
        is False
    )


def test_database_is_empty_rejects_incomplete_schema_at_current_head(monkeypatch):
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

    with pytest.raises(RuntimeError, match="current Alembic head.*incomplete"):
        migration_runner._database_is_empty(
            FakeEngine(),
            frozenset({"ffpi_revision"}),
            frozenset({"ffpi_revision"}),
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
        ("partial_at_head", None, "current Alembic head.*incomplete"),
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
        elif database_state in {"established", "partial_at_head"}:
            application_tables = (
                migration_runner.FFPI_APPLICATION_TABLES
                if database_state == "established"
                else {"users"}
            )
            for table_name in application_tables:
                Table(table_name, metadata, Column("id", Integer))
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

        if database_state in {
            "established",
            "partial_at_head",
            "foreign_history",
        }:
            revision = (
                "ffpi_revision"
                if database_state in {"established", "partial_at_head"}
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
                    frozenset({"ffpi_revision"}),
                )
        else:
            assert (
                migration_runner._database_is_empty(
                    test_engine,
                    frozenset({"ffpi_revision"}),
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


def test_bootstrap_and_incremental_migrations_produce_equivalent_schema(
    monkeypatch,
):
    database_url = os.getenv("FFPI_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("FFPI_TEST_POSTGRES_URL is not configured")

    schema_suffix = uuid4().hex
    bootstrap_database = f"ffpi_issue504_bootstrap_{schema_suffix}"
    incremental_database = f"ffpi_issue504_incremental_{schema_suffix}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    bootstrap_engine = None
    incremental_engine = None
    created_databases = []
    try:
        with admin_engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            for database_name in (bootstrap_database, incremental_database):
                quoted_name = admin_engine.dialect.identifier_preparer.quote(
                    database_name
                )
                connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
                created_databases.append(database_name)

        bootstrap_url = _migration_url_for_database(
            database_url, bootstrap_database
        )
        incremental_url = _migration_url_for_database(
            database_url, incremental_database
        )
        bootstrap_engine = create_engine(bootstrap_url, pool_pre_ping=True)
        incremental_engine = create_engine(incremental_url, pool_pre_ping=True)

        baseline_path = (
            Path(__file__).resolve().parents[2]
            / "db"
            / "test_fixtures"
            / "pre_0001_legacy_schema.sql"
        )
        baseline_sql = "\n".join(
            line
            for line in baseline_path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("--")
        )
        with incremental_engine.begin() as connection:
            for statement in baseline_sql.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)
            player_id = connection.execute(
                text(
                    "INSERT INTO players (name, gsis_id) "
                    "VALUES (:name, :gsis_id) RETURNING id"
                ),
                {
                    "name": "Issue 504 migration preservation probe",
                    "gsis_id": "issue504",
                },
            ).scalar_one()

        with monkeypatch.context() as scoped_environment:
            scoped_environment.setenv("DATABASE_URL", incremental_url)
            command.upgrade(
                Config(str(migration_runner.ALEMBIC_CONFIG_PATH)),
                "0001_create_draft_value_tables",
            )
            assert _alembic_versions(incremental_engine) == frozenset(
                {"0001_create_draft_value_tables"}
            )
            migration_runner.apply_migrations()

        with monkeypatch.context() as scoped_environment:
            scoped_environment.setenv("DATABASE_URL", bootstrap_url)
            migration_runner.apply_migrations()

        expected_heads = migration_runner._head_revisions(
            Config(str(migration_runner.ALEMBIC_CONFIG_PATH))
        )
        assert _alembic_versions(bootstrap_engine) == expected_heads
        assert _alembic_versions(incremental_engine) == expected_heads
        longest_revision_length = max(
            map(
                len,
                migration_runner._known_revisions(
                    Config(str(migration_runner.ALEMBIC_CONFIG_PATH))
                ),
            )
        )
        assert (
            _alembic_version_column_length(bootstrap_engine)
            >= longest_revision_length
        )
        assert (
            _alembic_version_column_length(incremental_engine)
            >= longest_revision_length
        )

        with incremental_engine.connect() as connection:
            preserved_player = connection.execute(
                text("SELECT name, gsis_id FROM players WHERE id = :player_id"),
                {"player_id": player_id},
            ).one()
        assert preserved_player == (
            "Issue 504 migration preservation probe",
            "issue504",
        )

        bootstrap_snapshot = _migration_schema_snapshot(bootstrap_engine)
        incremental_snapshot = _migration_schema_snapshot(incremental_engine)
        assert incremental_snapshot == bootstrap_snapshot

        with incremental_engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE players ADD COLUMN issue504_mismatch_probe INTEGER"
            )
        assert _migration_schema_snapshot(incremental_engine) != bootstrap_snapshot
    finally:
        if bootstrap_engine is not None:
            bootstrap_engine.dispose()
        if incremental_engine is not None:
            incremental_engine.dispose()
        with admin_engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            for database_name in created_databases:
                quoted_name = admin_engine.dialect.identifier_preparer.quote(
                    database_name
                )
                connection.exec_driver_sql(
                    f"DROP DATABASE IF EXISTS {quoted_name} WITH (FORCE)"
                )
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
        lambda _engine, _revisions, _heads: False,
    )
    monkeypatch.setattr(
        migration_runner,
        "_known_revisions",
        lambda _config: frozenset({"ffpi_revision"}),
    )
    monkeypatch.setattr(
        migration_runner,
        "_head_revisions",
        lambda _config: frozenset({"ffpi_revision"}),
    )
    monkeypatch.setattr(
        migration_runner,
        "_ensure_version_column_capacity",
        lambda _engine, _revisions: calls.append(("ensure_version_capacity",)),
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
    assert ("ensure_version_capacity",) in calls
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
        lambda _engine, _revisions, _heads: True,
    )
    monkeypatch.setattr(
        migration_runner,
        "_known_revisions",
        lambda _config: frozenset({"ffpi_revision"}),
    )
    monkeypatch.setattr(
        migration_runner,
        "_head_revisions",
        lambda _config: frozenset({"ffpi_revision"}),
    )
    monkeypatch.setattr(
        migration_runner,
        "_ensure_version_column_capacity",
        lambda _engine, _revisions: calls.append(("ensure_version_capacity",)),
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
    assert ("ensure_version_capacity",) in calls
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
        migration_runner,
        "_head_revisions",
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
