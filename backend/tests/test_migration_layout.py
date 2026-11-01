from pathlib import Path
from configparser import ConfigParser

import pytest

from scripts.validate_migration_layout import (
    find_noncanonical_revision_files,
    find_revision_files,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_alembic_config_uses_the_canonical_db_layout():
    config = ConfigParser()
    config.read(REPOSITORY_ROOT / "backend" / "alembic.ini")

    assert config.get("alembic", "script_location", raw=True) == "%(here)s/../db"
    assert (
        config.get("alembic", "version_locations", raw=True)
        == "%(here)s/../db/migrations"
    )


def test_legacy_alembic_revision_tree_is_absent():
    legacy_alembic = REPOSITORY_ROOT / "backend" / "alembic"

    assert not (legacy_alembic / "env.py").exists()
    assert not list((legacy_alembic / "versions").glob("*.py"))


def test_repository_revision_files_use_governed_locations():
    assert find_noncanonical_revision_files(REPOSITORY_ROOT) == []


@pytest.mark.parametrize(
    "relative_path",
    [
        Path("db/versions/unregistered_revision.py"),
        Path("backend/alembic/versions/unregistered_revision.py"),
        Path("backend/migrations/unregistered_revision.py"),
    ],
)
def test_revision_files_outside_canonical_locations_are_rejected(
    tmp_path, relative_path
):
    revision_file = tmp_path / relative_path
    revision_file.parent.mkdir(parents=True)
    revision_file.write_text('revision = "unregistered"\n', encoding="utf-8")

    assert find_noncanonical_revision_files(tmp_path) == [relative_path]


def test_canonical_and_governed_bootstrap_revisions_are_allowed(tmp_path):
    canonical = tmp_path / "db" / "migrations" / "new_revision.py"
    bootstrap = (
        tmp_path
        / "db"
        / "bootstrap"
        / "versions"
        / "0001_create_schema_at_0028.py"
    )
    for revision_file in (canonical, bootstrap):
        revision_file.parent.mkdir(parents=True, exist_ok=True)
        revision_file.write_text('revision = "allowed"\n', encoding="utf-8")

    assert len(find_revision_files(tmp_path)) == 2
    assert find_noncanonical_revision_files(tmp_path) == []