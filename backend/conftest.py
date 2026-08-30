"""
Pytest configuration for backend tests.
Database initialization is owned by the repository-root conftest.
"""

from contextlib import asynccontextmanager
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient


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


@pytest.fixture
def client():
    """Return a TestClient without running startup/lifespan events.

    Older versions of TestClient (used in GH Actions) lack the
    ``manage_lifespan`` keyword, so we temporarily disable the app's
    lifespan context instead.
    """
    from .main import app

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
    from .main import app

    with TestClient(app) as c:
        yield c
