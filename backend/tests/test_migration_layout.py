from configparser import ConfigParser
from pathlib import Path


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