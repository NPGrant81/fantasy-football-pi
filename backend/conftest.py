"""
Pytest configuration for backend tests.
This file sets up test fixtures and handles database initialization.
"""

import pytest
import os
from unittest.mock import Mock, patch


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Setup test environment before running tests.
    This ensures that database connection attempts during module import don't fail.
    """
    # Set a marker to indicate we're in test mode
    os.environ["TESTING"] = "true"
    
    # Mock the database URL to avoid connection attempts
    # This will be used if any code tries to connect during import
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    
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


@pytest.fixture
def client():
    """Return a TestClient without running startup/lifespan events.

    Older versions of TestClient (used in GH Actions) lack the
    ``manage_lifespan`` keyword, so we temporarily disable the app's
    lifespan context instead.
    """
    # stash the real lifespan context so we can restore it afterwards
    original = app.router.lifespan_context

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
