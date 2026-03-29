import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core.security import get_current_user
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


def _make_league_user(api_db):
    league = models.League(name="Gap API League")
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)

    user = models.User(
        username="gap-api-user",
        email="gap-api-user@test.com",
        hashed_password="hashed",
        league_id=league.id,
        is_commissioner=True,
    )
    api_db.add(user)
    api_db.commit()
    api_db.refresh(user)
    return league, user


def test_owner_gap_report_rejects_invalid_limit_query_params(client, api_db):
    league, user = _make_league_user(api_db)
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        responses = [
            client.get(f"/leagues/{league.id}/history/owner-gap-report?detail_limit=0"),
            client.get(f"/leagues/{league.id}/history/owner-gap-report?detail_limit=5001"),
            client.get(f"/leagues/{league.id}/history/owner-gap-report?detail_limit=abc"),
            client.get(f"/leagues/{league.id}/history/owner-gap-report?season_limit=0"),
            client.get(f"/leagues/{league.id}/history/owner-gap-report?season_limit=201"),
        ]
    finally:
        app.dependency_overrides.clear()

    assert all(response.status_code == 422 for response in responses)


def test_owner_gap_report_accepts_valid_limits_and_returns_metadata(client, api_db):
    league, user = _make_league_user(api_db)
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        response = client.get(
            f"/leagues/{league.id}/history/owner-gap-report?detail_limit=2&season_limit=2"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["league_id"] == league.id
    assert body["metadata"]["response_limits"] == {
        "detail_limit": 2,
        "season_limit": 2,
    }
    assert body["summary"] == {
        "placeholder_mapping_count": 0,
        "unresolved_match_team_count": 0,
        "unresolved_series_team_count": 0,
        "unresolved_series_source_token_count": 0,
        "season_count": 0,
    }
