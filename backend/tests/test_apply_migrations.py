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
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

from backend import apply_migrations as migration_runner
from backend import legacy_schema_bridge as bridge
from backend.legacy_schema_bridge import (
    ARCHIVE_SCHEMA,
    LegacyScoringMapping,
    finalize_legacy_schema_adoption,
    inspect_legacy_database,
    prepare_legacy_schema,
    reconcile_adopted_schema,
)


def _passing_td_mapping(rule_id):
    return LegacyScoringMapping(
        rule_id=rule_id,
        event_name="passing_tds",
        calculation_type="per_unit",
        range_min="0",
        range_max="9999.99",
        applicable_positions=["QB"],
    )


def _assert_write_blocked(engine, statement):
    with pytest.raises(DBAPIError) as error:
        with engine.begin() as writer:
            writer.exec_driver_sql("SET LOCAL lock_timeout = '100ms'")
            writer.exec_driver_sql(statement)
    assert error.value.orig.pgcode == "55P03"


@pytest.mark.parametrize(
    "changes",
    [
        {"event_name": "Passing TD"},
        {"event_name": "unknown_stat"},
        {"event_name": "fantasy_points"},
        {"calculation_type": "unknown"},
        {"calculation_type": "flat_bonus"},
        {"range_min": "10", "range_max": "1"},
        {"range_min": "NaN"},
        {"range_max": "Infinity"},
        {"range_min": "0.001"},
        {"applicable_positions": []},
        {"applicable_positions": ["unknown"]},
    ],
)
def test_legacy_scoring_mapping_rejects_unestablished_semantics(changes):
    from pydantic import ValidationError

    payload = _passing_td_mapping(1).model_dump()
    payload.update(changes)
    with pytest.raises(ValidationError):
        LegacyScoringMapping.model_validate(payload)


def test_legacy_scoring_mapping_accepts_explicit_nonzero_bonus():
    payload = _passing_td_mapping(1).model_dump()
    payload.update(calculation_type="flat_bonus", range_min="3")
    mapping = LegacyScoringMapping.model_validate(payload)
    assert mapping.range_min == 3


@pytest.mark.parametrize("apply", [False, True])
def test_legacy_adoption_cli_passes_reviewed_mappings(tmp_path, monkeypatch, apply):
    from backend import adopt_legacy_schema as adoption_cli

    mapping = _passing_td_mapping(42)
    mapping_file = tmp_path / "scoring.json"
    mapping_file.write_text(f"[{mapping.model_dump_json()}]", encoding="utf-8")
    calls = []

    class FakeEngine:
        def dispose(self):
            calls.append("disposed")

    def inspect_target(engine, *, scoring_mappings):
        assert scoring_mappings == (mapping,)
        return bridge.LegacyAdoptionReport(
            database="test_target",
            phase="validated:probe",
            table_row_counts=(),
            scoring_rule_rows=1,
            division_groups=0,
            bridge_managed_tables=(),
        )

    monkeypatch.setattr(
        adoption_cli,
        "resolve_database_url",
        lambda **kwargs: "postgresql://localhost/test_target",
    )
    monkeypatch.setattr(
        adoption_cli, "create_engine", lambda *args, **kwargs: FakeEngine()
    )
    monkeypatch.setattr(adoption_cli, "inspect_legacy_database", inspect_target)
    monkeypatch.setattr(
        adoption_cli,
        "_run_adoption",
        lambda url, mappings: calls.append((url, mappings)),
    )
    args = ["--scoring-mappings", str(mapping_file)]
    if apply:
        args.extend(["--apply", "--confirm-database", "test_target"])
    assert adoption_cli.main(args) == 0
    assert calls == (
        ["disposed", ("postgresql://localhost/test_target", (mapping,))]
        if apply
        else ["disposed"]
    )


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
        connection.exec_driver_sql(f"ALTER SEQUENCE snapshot_probe_id_seq {alteration}")
    assert _migration_schema_snapshot(engine)["sequences"] != baseline["sequences"]


def test_schema_snapshot_ignores_sequence_runtime_state(schema_snapshot_engine):
    engine = schema_snapshot_engine
    baseline = _migration_schema_snapshot(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO snapshot_probe (payload) VALUES ('{}')")
        connection.exec_driver_sql("SELECT setval('snapshot_probe_id_seq', 50, true)")
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
                    metadata.tables["alembic_version"]
                    .insert()
                    .values(version_num=revision)
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

        bootstrap_url = _migration_url_for_database(database_url, bootstrap_database)
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
            league_id = connection.execute(
                text(
                    "INSERT INTO leagues (name) "
                    "VALUES ('Issue 554 test league') RETURNING id"
                )
            ).scalar_one()
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
            user_id = connection.execute(
                text(
                    "INSERT INTO users (username, league_id, division) "
                    "VALUES ('issue554-owner', :league_id, 'East') RETURNING id"
                ),
                {"league_id": league_id},
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO league_settings (league_id, roster_size, salary_cap) "
                    "VALUES (:league_id, 16, 200)"
                ),
                {"league_id": league_id},
            )
            scoring_rule_id = connection.execute(
                text(
                    "INSERT INTO scoring_rules "
                    "(league_id, category, description, points) "
                    "VALUES (:league_id, 'passing', 'Passing TD', 4.0) "
                    "RETURNING id"
                ),
                {"league_id": league_id},
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO player_weekly_stats "
                    "(player_id, season, week, fantasy_points, source) "
                    "VALUES (:player_id, 2025, 1, 12.5, 'test')"
                ),
                {"player_id": player_id},
            )
            connection.execute(
                text(
                    "INSERT INTO draft_picks "
                    "(year, round_num, pick_num, owner_id, player_id, league_id) "
                    "VALUES (2025, 1, 1, :user_id, :player_id, :league_id)"
                ),
                {
                    "user_id": user_id,
                    "player_id": player_id,
                    "league_id": league_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO draft_budgets "
                    "(league_id, owner_id, year, total_budget) "
                    "VALUES (:league_id, :user_id, 2025, 200)"
                ),
                {"league_id": league_id, "user_id": user_id},
            )
            connection.execute(
                text(
                    "INSERT INTO matchups "
                    "(league_id, week, home_team_id, away_team_id) "
                    "VALUES (:league_id, 1, :user_id, :user_id)"
                ),
                {"league_id": league_id, "user_id": user_id},
            )
            connection.execute(
                text(
                    "INSERT INTO waiver_claims "
                    "(league_id, user_id, player_id, bid_amount) "
                    "VALUES (:league_id, :user_id, :player_id, 7)"
                ),
                {
                    "league_id": league_id,
                    "user_id": user_id,
                    "player_id": player_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO bug_reports "
                    "(user_id, title, description) "
                    "VALUES (:user_id, 'Issue 554 probe', 'Preserve this legacy row')"
                ),
                {"user_id": user_id},
            )
            connection.execute(
                text(
                    "INSERT INTO trade_proposals "
                    "(league_id, from_user_id, to_user_id, offered_player_id, "
                    "requested_player_id) "
                    "VALUES (:league_id, :user_id, :user_id, :player_id, :player_id)"
                ),
                {
                    "league_id": league_id,
                    "user_id": user_id,
                    "player_id": player_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO lineup_submissions "
                    "(league_id, owner_id, season, week) "
                    "VALUES (:league_id, :user_id, 2025, 1)"
                ),
                {"league_id": league_id, "user_id": user_id},
            )

        mappings = (_passing_td_mapping(scoring_rule_id),)
        report = inspect_legacy_database(incremental_engine, scoring_mappings=mappings)
        assert report.phase.startswith("validated:")
        assert report.scoring_rule_rows == 1
        assert report.division_groups == 1

        with monkeypatch.context() as scoped_environment:
            scoped_environment.setenv("DATABASE_URL", incremental_url)
            original_validate = bridge._validate_scoring_rule_mapping

            def validate_while_locked(connection, schema, scoring_mappings):
                result = original_validate(connection, schema, scoring_mappings)
                locked_tables = set(
                    connection.execute(
                        text(
                            "SELECT c.relname FROM pg_locks l JOIN pg_class c "
                            "ON c.oid = l.relation JOIN pg_namespace n ON n.oid = c.relnamespace "
                            "WHERE l.pid = pg_backend_pid() AND l.granted "
                            "AND l.mode = 'AccessExclusiveLock' AND n.nspname = 'public'"
                        )
                    ).scalars()
                )
                assert bridge.LEGACY_TABLES <= locked_tables
                _assert_write_blocked(
                    incremental_engine, "UPDATE scoring_rules SET points = 4.001"
                )
                return result

            scoped_environment.setattr(
                bridge, "_validate_scoring_rule_mapping", validate_while_locked
            )
            prepared_report = prepare_legacy_schema(
                incremental_engine, scoring_mappings=mappings
            )
            assert prepared_report.phase.startswith("prepared:")
            resumed_report = prepare_legacy_schema(incremental_engine)
            assert resumed_report.phase == f"resume:{prepared_report.phase}"
            command.upgrade(
                Config(str(migration_runner.ALEMBIC_CONFIG_PATH)),
                "0001_create_draft_value_tables",
            )
            assert _alembic_versions(incremental_engine) == frozenset(
                {"0001_create_draft_value_tables"}
            )
            migration_runner.apply_migrations()
        with incremental_engine.begin() as connection:
            bridge._archive_reconciliation_data(connection, {"manual_player_mappings"})
            assert "reconcile_manual_player_mappings" not in inspect(
                connection
            ).get_table_names(schema=ARCHIVE_SCHEMA)
            _assert_write_blocked(
                incremental_engine, "INSERT INTO manual_player_mappings DEFAULT VALUES"
            )
            connection.execute(
                text(
                    "INSERT INTO manual_player_mappings "
                    "(source_name, scraped_player_name, true_player_id, "
                    "scraped_name, player_id) "
                    "VALUES ('equivalence-probe', 'Archived mapping', "
                    ":player_id, 'Archived mapping', :player_id)"
                ),
                {"player_id": player_id},
            )
        with monkeypatch.context() as scoped_environment:
            original_archive = bridge._archive_reconciliation_data

            def archive_while_locked(connection, tables):
                original_archive(connection, tables)
                assert "manual_player_mappings" in tables
                _assert_write_blocked(
                    incremental_engine,
                    "UPDATE manual_player_mappings SET source_name = 'lost-write'",
                )

            scoped_environment.setattr(
                bridge, "_archive_reconciliation_data", archive_while_locked
            )
            reconcile_adopted_schema(incremental_engine)
        finalize_legacy_schema_adoption(incremental_engine)

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
            _alembic_version_column_length(bootstrap_engine) >= longest_revision_length
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
        with incremental_engine.connect() as connection:
            preserved_rule = connection.execute(
                text(
                    "SELECT category, event_name, point_value::float8, "
                    "range_min::float8, range_max::float8, "
                    "calculation_type, applicable_positions FROM scoring_rules "
                    "WHERE id = :rule_id"
                ),
                {"rule_id": scoring_rule_id},
            ).one()
            preserved_division = connection.execute(
                text(
                    "SELECT division.name FROM users "
                    "JOIN divisions AS division ON division.id = users.division_id "
                    "WHERE users.id = :user_id"
                ),
                {"user_id": user_id},
            ).scalar_one()
            archived_division = connection.execute(
                text(
                    f"SELECT division FROM {ARCHIVE_SCHEMA}.users "
                    "WHERE id = :user_id"
                ),
                {"user_id": user_id},
            ).scalar_one()
            archived_points = connection.execute(
                text(
                    f"SELECT points FROM {ARCHIVE_SCHEMA}.scoring_rules "
                    "WHERE id = :rule_id"
                ),
                {"rule_id": scoring_rule_id},
            ).scalar_one()
            archived_mapping = connection.execute(
                text(
                    f"SELECT source_name, scraped_player_name, true_player_id "
                    f"FROM {ARCHIVE_SCHEMA}.reconcile_manual_player_mappings "
                    "WHERE source_name = 'equivalence-probe'"
                )
            ).one()
            mapping_columns = {
                column["name"]
                for column in inspect(incremental_engine).get_columns(
                    "manual_player_mappings"
                )
            }
            archived_counts = {
                table: connection.execute(
                    text(f"SELECT count(*) FROM {ARCHIVE_SCHEMA}.{table}")
                ).scalar_one()
                for table in sorted(
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
            }
            archived_user_foreign_keys = inspect(incremental_engine).get_foreign_keys(
                "users",
                schema=ARCHIVE_SCHEMA,
            )
        assert preserved_rule == (
            "passing",
            "passing_tds",
            4,
            0,
            9999.99,
            "per_unit",
            ["QB"],
        )
        from sqlalchemy.orm import Session
        from backend.models import ScoringRule
        from backend.services.scoring_service import calculate_points_for_stats

        with Session(incremental_engine) as session:
            rule = session.get(ScoringRule, scoring_rule_id)
            assert rule.is_active
            for stats, position, expected_points in (
                ({}, "QB", 0),
                ({"passing_tds": 0}, "QB", 0),
                ({"passing_tds": 1}, "QB", 4),
                ({"passing_tds": 2}, "QB", 8),
                ({"passing_tds": 2}, "RB", 0),
            ):
                points, _ = calculate_points_for_stats(
                    stats=stats, position=position, rules=[rule]
                )
                assert points == expected_points
        assert preserved_division == "East"
        assert archived_division == "East"
        assert archived_points == 4.0
        assert archived_mapping == ("equivalence-probe", "Archived mapping", player_id)
        assert "source_name" not in mapping_columns
        assert "scraped_player_name" not in mapping_columns
        assert "true_player_id" not in mapping_columns
        assert any(
            foreign_key["referred_schema"] == ARCHIVE_SCHEMA
            and foreign_key["referred_table"] == "leagues"
            for foreign_key in archived_user_foreign_keys
        )
        assert archived_counts == {
            "bug_reports": 1,
            "draft_budgets": 1,
            "draft_picks": 1,
            "leagues": 1,
            "league_settings": 1,
            "lineup_submissions": 1,
            "matchups": 1,
            "player_weekly_stats": 1,
            "players": 1,
            "scoring_rules": 1,
            "trade_proposals": 1,
            "users": 1,
            "waiver_claims": 1,
        }

        bootstrap_snapshot = _migration_schema_snapshot(bootstrap_engine)
        incremental_snapshot = _migration_schema_snapshot(incremental_engine)
        schema_differences = {
            table_name: {
                part: {
                    "incremental": incremental_snapshot.get(table_name, {}).get(part),
                    "bootstrap": bootstrap_snapshot.get(table_name, {}).get(part),
                }
                for part in set(incremental_snapshot.get(table_name, {}))
                | set(bootstrap_snapshot.get(table_name, {}))
                if incremental_snapshot.get(table_name, {}).get(part)
                != bootstrap_snapshot.get(table_name, {}).get(part)
            }
            for table_name in set(incremental_snapshot) | set(bootstrap_snapshot)
            if incremental_snapshot.get(table_name)
            != bootstrap_snapshot.get(table_name)
        }
        assert (
            not schema_differences
        ), f"Bootstrap/incremental schema differences: {schema_differences}"

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


@pytest.mark.parametrize(
    "invalid_case",
    [
        "unexpected_column",
        "unmappable_scoring_rule",
        "cross_schema_fk",
        "missing_mapping",
        "duplicate_mapping",
        "extra_mapping",
        "null_season",
        "null_week",
    ],
)
def test_legacy_adoption_rejects_unsupported_source_without_archiving(
    invalid_case,
):
    database_url = os.getenv("FFPI_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("FFPI_TEST_POSTGRES_URL is not configured")

    database_name = f"ffpi_issue554_reject_{uuid4().hex}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    test_engine = None
    try:
        with admin_engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            quoted_name = admin_engine.dialect.identifier_preparer.quote(database_name)
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")

        test_engine = create_engine(
            _migration_url_for_database(database_url, database_name),
            pool_pre_ping=True,
        )
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
        with test_engine.begin() as connection:
            for statement in baseline_sql.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)
            if invalid_case == "unexpected_column":
                connection.exec_driver_sql(
                    "ALTER TABLE players ADD COLUMN unexpected_source_column TEXT"
                )
            elif invalid_case == "cross_schema_fk":
                connection.exec_driver_sql("CREATE SCHEMA other")
                connection.exec_driver_sql(
                    "CREATE TABLE other.leagues (id INTEGER PRIMARY KEY)"
                )
                connection.exec_driver_sql(
                    "ALTER TABLE users DROP CONSTRAINT users_league_id_fkey"
                )
                connection.exec_driver_sql(
                    "ALTER TABLE users ADD CONSTRAINT users_league_id_fkey "
                    "FOREIGN KEY (league_id) REFERENCES other.leagues(id)"
                )
            else:
                league_id = connection.execute(
                    text(
                        "INSERT INTO leagues (name) VALUES ('Invalid mapping') "
                        "RETURNING id"
                    )
                ).scalar_one()
                if invalid_case in {"null_season", "null_week"}:
                    user_id = connection.execute(
                        text(
                            "INSERT INTO users (username, league_id) "
                            "VALUES ('lineup-probe', :league_id) RETURNING id"
                        ),
                        {"league_id": league_id},
                    ).scalar_one()
                    connection.execute(
                        text(
                            "INSERT INTO lineup_submissions (league_id, owner_id, season, week) "
                            "VALUES (:league_id, :user_id, :season, :week)"
                        ),
                        {
                            "league_id": league_id,
                            "user_id": user_id,
                            "season": None if invalid_case == "null_season" else 2025,
                            "week": None if invalid_case == "null_week" else 1,
                        },
                    )
                else:
                    connection.execute(
                        text(
                            "INSERT INTO scoring_rules "
                            "(league_id, category, description, points) "
                            "VALUES (:league_id, 'passing', 'Passing TD', :points)"
                        ),
                        {
                            "league_id": league_id,
                            "points": (
                                None if invalid_case == "unmappable_scoring_rule" else 4
                            ),
                        },
                    )

        expected_error = (
            "differs from the pinned fixture"
            if invalid_case in {"unexpected_column", "cross_schema_fk"}
            else (
                "NULL season or week"
                if invalid_case in {"null_season", "null_week"}
                else "Cannot map"
            )
        )
        mappings = (
            (_passing_td_mapping(1), _passing_td_mapping(1))
            if invalid_case == "duplicate_mapping"
            else (
                (_passing_td_mapping(1), _passing_td_mapping(2))
                if invalid_case == "extra_mapping"
                else ()
            )
        )
        source_snapshot = _migration_schema_snapshot(test_engine)
        for operation in (inspect_legacy_database, prepare_legacy_schema):
            with pytest.raises(RuntimeError, match=expected_error):
                operation(test_engine, scoring_mappings=mappings)
            assert _migration_schema_snapshot(test_engine) == source_snapshot

        assert ARCHIVE_SCHEMA not in inspect(test_engine).get_schema_names()
        assert "alembic_version" not in inspect(test_engine).get_table_names()
        if invalid_case == "unexpected_column":
            assert "unexpected_source_column" in {
                column["name"] for column in inspect(test_engine).get_columns("players")
            }
    finally:
        if test_engine is not None:
            test_engine.dispose()
        with admin_engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            quoted_name = admin_engine.dialect.identifier_preparer.quote(database_name)
            connection.exec_driver_sql(
                f"DROP DATABASE IF EXISTS {quoted_name} WITH (FORCE)"
            )
        admin_engine.dispose()


def test_apply_migrations_upgrades_all_heads_for_established_database(
    monkeypatch, tmp_path
):
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
