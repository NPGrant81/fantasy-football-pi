"""Repository-wide pytest environment and database lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import pytest

from _pytest_support import backend_tests_requested


_test_database_directory: TemporaryDirectory[str] | None = None

os.environ["TESTING"] = "1"


repository_root = Path(__file__).resolve().parent
_backend_tests_selected = backend_tests_requested(sys.argv[1:], repository_root)
if _backend_tests_selected:
    use_configured_database = (
        os.getenv("FFPI_PYTEST_USE_CONFIGURED_DATABASE") == "1"
    )
    running_in_github_actions = (
        os.getenv("CI", "").lower() == "true"
        and os.getenv("GITHUB_ACTIONS", "").lower() == "true"
    )
    if use_configured_database and not running_in_github_actions:
        raise RuntimeError(
            "FFPI_PYTEST_USE_CONFIGURED_DATABASE=1 is restricted to GitHub Actions"
        )
    if use_configured_database and "DATABASE_URL" not in os.environ:
        raise RuntimeError(
            "FFPI_PYTEST_USE_CONFIGURED_DATABASE=1 requires an explicit DATABASE_URL"
        )
    if not use_configured_database:
        _test_database_directory = TemporaryDirectory(prefix="ffpi-pytest-")
        database_path = Path(_test_database_directory.name) / "backend.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
        os.environ["FFPI_PYTEST_OWNS_DATABASE"] = "1"
    else:
        os.environ.pop("FFPI_PYTEST_OWNS_DATABASE", None)


@pytest.fixture(scope="session", autouse=True)
def test_database_lifecycle():
    """Initialize and dispose only the SQLite database created for this run."""
    if not _backend_tests_selected or _test_database_directory is None:
        yield
        return

    database_engine = None
    try:
        from backend import models, models_draft_value  # noqa: F401
        from backend.database import Base, engine

        database_engine = engine
        Base.metadata.create_all(bind=database_engine)
        yield
    finally:
        if database_engine is not None:
            database_engine.dispose()
        _test_database_directory.cleanup()
