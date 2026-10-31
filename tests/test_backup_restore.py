import gzip
import os
import sqlite3
from pathlib import Path
import shutil

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from scripts.verify_backup_restore import verify_restore


def test_missing_sqlite_source_is_not_created(tmp_path):
    source = tmp_path / "missing.sqlite"
    archive = tmp_path / "backup.sqlite"
    archive.write_bytes(b"archive")
    with pytest.raises(FileNotFoundError):
        verify_restore(f"sqlite:///{source.as_posix()}", archive)
    assert not source.exists()


def make_backup(tmp_path: Path) -> tuple[str, Path, Path]:
    source = tmp_path / "source.sqlite"
    url = f"sqlite:///{source.as_posix()}"
    engine = create_engine(url)
    metadata = MetaData()
    table = Table("evidence", metadata, Column("id", Integer, primary_key=True), Column("name", String))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(table.insert(), [{"id": 1, "name": "retained"}])
    engine.dispose()
    archive = tmp_path / "backup.sqlite.gz"
    with source.open("rb") as raw, gzip.open(archive, "wb") as target:
        shutil.copyfileobj(raw, target)
    return url, source, archive


def test_restores_real_archive_without_modifying_source(tmp_path):
    url, source, archive = make_backup(tmp_path)
    before = source.read_bytes()
    assert verify_restore(url, archive) == 1
    assert source.read_bytes() == before


def test_rejects_corrupt_archive(tmp_path):
    url, source, archive = make_backup(tmp_path)
    before = source.read_bytes()
    archive.write_bytes(b"not a gzip archive")
    with pytest.raises(gzip.BadGzipFile):
        verify_restore(url, archive)
    assert source.read_bytes() == before


def test_rejects_valid_gzip_with_invalid_database(tmp_path):
    url, _, archive = make_backup(tmp_path)
    with gzip.open(archive, "wb") as target:
        target.write(b"not a database")
    with pytest.raises(Exception, match="not a database"):
        verify_restore(url, archive)


def test_detects_restored_data_mismatch(tmp_path):
    url, source, archive = make_backup(tmp_path)
    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE evidence SET name = ?", ("changed",))
    with pytest.raises(RuntimeError, match="sampled data"):
        verify_restore(url, archive)


def test_postgres_create_failure_does_not_drop_any_database(tmp_path, monkeypatch):
    import scripts.verify_backup_restore as drill

    archive = tmp_path / "backup.dump"
    archive.write_bytes(b"archive")
    monkeypatch.setattr(drill, "create_engine", lambda _: type("Engine", (), {"dispose": lambda self: None})())
    monkeypatch.setattr(drill, "database_manifest", lambda _: {"table": ((), 1, "digest")})
    commands = []

    def fail_create(command, password):
        commands.append(command)
        raise RuntimeError("create failed")

    monkeypatch.setattr(drill, "_postgres_command", fail_create)
    with pytest.raises(RuntimeError, match="create failed"):
        verify_restore("postgresql://user:password@localhost/source", archive)
    assert len(commands) == 1
    assert commands[0][0] == "createdb"
    assert commands[0][-1].startswith("ffpi_recovery_")
    assert "password" not in repr(commands)


@pytest.mark.parametrize("restore_fails", [False, True])
def test_postgres_drops_only_owned_database_even_when_restore_fails(tmp_path, monkeypatch, restore_fails):
    import scripts.verify_backup_restore as drill

    archive = tmp_path / "backup.dump"
    archive.write_bytes(b"archive")
    monkeypatch.setattr(drill, "create_engine", lambda _: type("Engine", (), {"dispose": lambda self: None})())
    monkeypatch.setattr(drill, "database_manifest", lambda _: {"table": ((), 1, "digest")})
    commands = []

    def run(command, password):
        commands.append(command)
        if command[0] == "pg_restore" and restore_fails:
            raise RuntimeError("restore failed")

    monkeypatch.setattr(drill, "_postgres_command", run)
    if restore_fails:
        with pytest.raises(RuntimeError, match="restore failed"):
            verify_restore("postgresql://user:password@localhost/source", archive)
    else:
        assert verify_restore("postgresql://user:password@localhost/source", archive) == 1
    assert [command[0] for command in commands] == ["createdb", "pg_restore", "dropdb"]
    owned_database = commands[0][-1]
    assert owned_database.startswith("ffpi_recovery_")
    assert commands[-1][-1] == owned_database
    assert owned_database in commands[1][-2]
    assert "password" not in repr(commands)


@pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("FFPI_TEST_POSTGRES_URL"),
    reason="Requires the owned GitHub Actions PostgreSQL service, never a developer database.",
)
def test_postgres_archive_round_trip_in_owned_ci_database(tmp_path):
    from uuid import uuid4

    from sqlalchemy.engine import make_url
    from scripts.verify_backup_restore import _postgres_command

    source = make_url(os.environ["FFPI_TEST_POSTGRES_URL"])
    assert source.get_backend_name() == "postgresql"
    source = source.set(database=f"ffpi_recovery_source_{uuid4().hex}")
    admin = source.set(database="postgres")._replace(password=None).render_as_string(hide_password=False)
    public_source = source._replace(password=None).render_as_string(hide_password=False)
    admin = admin.replace(source.drivername + ":", "postgresql:", 1)
    public_source = public_source.replace(source.drivername + ":", "postgresql:", 1)
    created = False
    try:
        _postgres_command(["createdb", "--maintenance-db", admin, source.database], source.password)
        created = True
        engine = create_engine(source)
        try:
            metadata = MetaData()
            table = Table("evidence", metadata, Column("id", Integer, primary_key=True), Column("name", String))
            metadata.create_all(engine)
            with engine.begin() as connection:
                connection.execute(table.insert(), [{"id": 1, "name": "retained"}])
        finally:
            engine.dispose()
        archive = tmp_path / "backup.dump"
        _postgres_command([
            "pg_dump", "--dbname", public_source, "--format=custom", "--file", str(archive),
        ], source.password)
        assert verify_restore(source.render_as_string(hide_password=False), archive) == 1
        engine = create_engine(source)
        try:
            with engine.connect() as connection:
                assert connection.execute(table.select()).one().name == "retained"
        finally:
            engine.dispose()
    finally:
        if created:
            _postgres_command(["dropdb", "--maintenance-db", admin, source.database], source.password)
