import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.database import get_db
from backend.main import app


@pytest.fixture
def api_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_dependencies(api_db):
    def override_get_db():
        try:
            yield api_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def test_analytics_boundaries_reject_out_of_range_and_malformed_query_params(client):
    out_of_range = client.get("/analytics/league/1/weekly-matchups?start_week=0&end_week=18")
    malformed = client.get("/analytics/league/1/leaderboard?season=not-a-year")

    assert out_of_range.status_code == 422
    assert malformed.status_code == 422


def test_visit_logging_creates_site_visit_record(client, api_db):
    payload = {
        "timestamp": "2026-03-11T10:15:30Z",
        "path": "/analytics",
        "userId": None,
        "sessionId": "test-session-12345",
        "userAgent": "pytest",
        "referrer": "http://localhost:5173/",
    }

    response = client.post("/analytics/visit", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body.get("id") is not None
    assert body.get("timestamp")

    rows = api_db.query(models.SiteVisit).all()
    assert len(rows) == 1
    assert rows[0].path == "/analytics"
    assert rows[0].session_id == "test-session-12345"
    assert rows[0].user_id is None


def test_visit_logging_rejects_invalid_path(client):
    response = client.post(
        "/analytics/visit",
        json={
            "timestamp": "2026-03-11T10:15:30Z",
            "path": "analytics",
            "sessionId": "test-session-12345",
        },
    )

    assert response.status_code == 422
