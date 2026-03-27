"""
Pytest configuration for backend tests.
This file sets up test fixtures and handles database initialization.
"""

import pytest
import os
from unittest.mock import Mock, patch


# Ensure app/database imports use a deterministic test DB URL.
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./pytest_backend.db"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Setup test environment before running tests.
    This ensures that database connection attempts during module import don't fail.
    """
    # Keep explicit markers for test-only branches in runtime code.
    os.environ["TESTING"] = "true"
    
    yield
    
    # Cleanup after tests
    if "TESTING" in os.environ:
        del os.environ["TESTING"]


@pytest.fixture
def mock_db():
    """
    Provide a mock database session for tests that need it.
    """
    db = Mock()
    db.query = Mock(return_value=Mock())
    return db


# ---------------------------------------------------------------------------
# TestClient fixtures to control lifespan behaviour
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from .main import app
from contextlib import asynccontextmanager


@pytest.fixture
def client():
    """Return a TestClient without running startup/lifespan events.

    Older versions of TestClient (used in GH Actions) lack the
    ``manage_lifespan`` keyword, so we temporarily disable the app's
    lifespan context instead.
    """
    # stash the real lifespan context so we can restore it afterwards
    original = app.router.lifespan_context

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app.router.lifespan_context = noop_lifespan
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.router.lifespan_context = original


@pytest.fixture
def integration_client():
    """Return a TestClient that executes the full lifespan.

    This is identical to ``client`` but deliberately *does not* override
    the lifespan context.  Use this sparingly in startup/integration tests.
    """
    with TestClient(app) as c:
        yield c
