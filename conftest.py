"""Repository-wide pytest environment and database lifecycle."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


_test_database_directory: TemporaryDirectory[str] | None = None

os.environ["TESTING"] = "1"
use_configured_database = os.getenv("FFPI_PYTEST_USE_CONFIGURED_DATABASE") == "1"
if use_configured_database and os.getenv("CI", "").lower() != "true":
    raise RuntimeError(
        "FFPI_PYTEST_USE_CONFIGURED_DATABASE=1 is restricted to CI test databases"
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
def test_database_lifecycle(request):
    """Initialize and dispose only the SQLite database created for this run."""
    if _test_database_directory is None:
        yield
        return

    backend_directory = Path(__file__).resolve().parent / "backend"
    backend_selected = any(
        Path(item.path).resolve().is_relative_to(backend_directory)
        for item in request.session.items
        if getattr(item, "path", None) is not None
    )
    database_engine = None
    try:
        if backend_selected:
            from backend import models, models_draft_value  # noqa: F401
            from backend.database import Base, engine

            database_engine = engine
            Base.metadata.create_all(bind=database_engine)
        yield
    finally:
        if database_engine is not None:
            database_engine.dispose()
        _test_database_directory.cleanup()
