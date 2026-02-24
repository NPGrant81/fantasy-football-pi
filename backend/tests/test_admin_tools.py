import os
# force tests to use sqlite in-memory database
os.environ['DATABASE_URL'] = 'sqlite://'

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from core.security import check_is_commissioner
from database import get_db
from backend.main import app


@pytest.fixture
def api_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db, TestingSessionLocal
    finally:
        db.close()


@pytest.fixture
def client(api_db):
    db, _ = api_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_import_schedule_denied_for_non_commissioner(client, api_db):
    # disable commissioner privileges
    async def deny_commissioner():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Commissioner privileges required.",
        )

    app.dependency_overrides[check_is_commissioner] = deny_commissioner

    response = client.post("/admin/tools/import-nfl-schedule", json={"year": 2025})
    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied. Commissioner privileges required."


def test_import_schedule_runs_upsert(client, api_db):
    # allow commission
    async def allow_commissioner():
        # dummy user object
        return models.User(username="c", email="c@test.com", hashed_password="x", is_commissioner=True)

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    # stub the upsert function so we can inspect calls
    import scripts.import_nfl_schedule as sched

    calls = []

    def fake_upsert(year, week=None):
        calls.append((year, week))

    sched.upsert_games = fake_upsert

    response = client.post("/admin/tools/import-nfl-schedule", json={"year": 2026, "week": 3})
    assert response.status_code == 200
    assert "Schedule import started" in response.json().get("detail", "")

    # background task should have queued our fake function; TestClient runs it synchronously
    assert calls == [(2026, 3)]
