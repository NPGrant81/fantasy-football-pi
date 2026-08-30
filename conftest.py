"""Repository-wide pytest environment and database lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


_test_database_directory: TemporaryDirectory[str] | None = None

os.environ.setdefault("TESTING", "true")
if "DATABASE_URL" not in os.environ:
    _test_database_directory = TemporaryDirectory(prefix="ffpi-pytest-")
    database_path = Path(_test_database_directory.name) / "backend.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
os.environ["FFPI_PYTEST_DATABASE_URL"] = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
def test_database_lifecycle():
    """Initialize and dispose only the SQLite database created for this run."""
    if _test_database_directory is None:
        yield
        return

    from backend import models, models_draft_value  # noqa: F401
    from backend.database import Base, engine

    Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        engine.dispose()
        _test_database_directory.cleanup()
