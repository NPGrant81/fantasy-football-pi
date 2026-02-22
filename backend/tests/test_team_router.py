import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from database import get_db
from main import app


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


def test_view_empty_team_returns_200(client, api_db):
    db, _ = api_db
    # create a user with no picks
    user = models.User(username='user1',
                       email='u1@test.com',
                       hashed_password='hashed',
                       is_commissioner=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    res = client.get(f'/team/{user.id}?week=1')
    assert res.status_code == 200
    body = res.json()
    assert body['owner_id'] == user.id
    assert isinstance(body.get('players'), list)
    assert body['players'] == []


def test_team_500_before_model_wouldhave_failed():
    # simply ensure the LineupSubmission class exists on startup
    assert hasattr(models, 'LineupSubmission'), "LineupSubmission model must exist"
