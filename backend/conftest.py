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

    This is the lightweight client that should be used by most backend
    unit tests.  It avoids the database seeder and slow schema setup so that
    the suite can run in milliseconds instead of seconds.
    """
    with TestClient(app, manage_lifespan=False) as c:
        yield c


@pytest.fixture
def integration_client():
    """Return a TestClient that executes the full lifespan.

    Only use this when a test cares about the startup behaviour (e.g.
    verifying that the admin user is seeded or runtime schemata are applied).
    """
    with TestClient(app, manage_lifespan=True) as c:
        yield c
