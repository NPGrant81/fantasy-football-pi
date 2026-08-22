from pathlib import Path

from backend import apply_migrations as migration_runner


def test_apply_migrations_upgrades_all_heads_for_established_database(monkeypatch, tmp_path):
    config_path = tmp_path / "alembic.ini"
    config_path.write_text("[alembic]\nscript_location = db\n", encoding="ascii")
    calls = []

    class FakeConfig:
        def __init__(self, path):
            calls.append(("config", path))

    monkeypatch.setattr(migration_runner, "Config", FakeConfig)
    monkeypatch.setattr(migration_runner, "_database_is_empty", lambda: False)
    monkeypatch.setattr(
        migration_runner.command,
        "upgrade",
        lambda config, revision: calls.append(("upgrade", config, revision)),
    )

    migration_runner.apply_migrations(config_path)

    assert calls[0] == ("config", str(config_path))
    assert calls[1][0] == "upgrade"
    assert calls[1][2] == "heads"


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

    monkeypatch.setattr(migration_runner, "Config", FakeConfig)
    monkeypatch.setattr(migration_runner, "_database_is_empty", lambda: True)
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


def test_default_alembic_config_exists():
    assert isinstance(migration_runner.ALEMBIC_CONFIG_PATH, Path)
    assert migration_runner.ALEMBIC_CONFIG_PATH.is_file()
