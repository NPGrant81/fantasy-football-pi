import os
# use sqlite for the engine during tests to avoid Postgres connection errors
os.environ['DATABASE_URL'] = 'sqlite://'

import os
# use sqlite for the engine during tests to avoid Postgres connection errors
os.environ['DATABASE_URL'] = 'sqlite://'

import pytest
from fastapi.testclient import TestClient

from backend import models
from backend.database import get_db
from backend.main import app


@pytest.fixture
def api_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(api_db):
    def override_get_db():
        try:
            yield api_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_empty_schedule(client):
    res = client.get("/nfl/schedule/2026/1")
    assert res.status_code == 200
    assert res.json() == []


def test_normalize_event_fallback_week():
    from scripts.import_nfl_schedule import normalize_event
    # create a fake event with no week key
    evt = {
        "id": "1000",
        "season": {"year": 2025},
        "competitions": [
            {
                # no 'week' sub-object
                "date": "2025-09-11T20:20:00Z",
                "competitors": [
                    {"team": {"id": 1}, "score": "0"},
                    {"team": {"id": 2}, "score": "0"},
                ],
                "status": {"type": {"name": "PRE"}},
            }
        ],
    }
    norm = normalize_event(evt)
    assert norm["week"] == 2  # Sep 11, 2025 should be week 2 (first Thu is Sep 4)


def test_upsert_handles_missing_week():
    """Normalization logic should supply a week when the raw event lacks it."""
    from scripts.import_nfl_schedule import normalize_event

    evt = {
        "id": "2000",
        "season": {"year": 2025},
        "competitions": [
            {
                "date": "2025-09-11T20:20:00Z",
                "competitors": [
                    {"team": {"id": 10}, "score": "0"},
                    {"team": {"id": 20}, "score": "0"},
                ],
                "status": {"type": {"name": "PRE"}},
            }
        ],
    }
    normalized = normalize_event(evt)
    assert normalized["week"] == 2


# we're not going to call the importer here; extending coverage would require
# mocking requests.  smoke test just ensures route exists and returns empty list.
