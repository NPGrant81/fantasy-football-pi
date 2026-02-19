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
