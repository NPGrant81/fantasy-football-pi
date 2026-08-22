from pathlib import Path

import pytest

from backend import apply_migrations as migration_runner


@pytest.mark.parametrize(
    ("table_names", "expected"),
    [
        ([], True),
        (["alembic_version"], True),
        (["monitoring_events"], True),
        (["alembic_version", "monitoring_events"], True),
        (["users"], False),
        (["monitoring_events", "players"], False),
    ],
)
def test_database_is_empty_ignores_unrelated_tables(monkeypatch, table_names, expected):
    class FakeInspector:
        def get_table_names(self):
            return table_names

    monkeypatch.setattr(
        migration_runner,
        "inspect",
        lambda _engine: FakeInspector(),
    )

    assert migration_runner._database_is_empty(object()) is expected


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
    monkeypatch.setattr(migration_runner, "_database_is_empty", lambda _engine: False)
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
    monkeypatch.setattr(migration_runner, "_database_is_empty", lambda _engine: True)
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


def test_default_alembic_config_exists():
    assert isinstance(migration_runner.ALEMBIC_CONFIG_PATH, Path)
    assert migration_runner.ALEMBIC_CONFIG_PATH.is_file()
