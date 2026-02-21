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
from core.security import check_is_commissioner
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


def test_remove_member_returns_403_when_commissioner_dependency_denies(client, api_db):
    db, _ = api_db

    league = models.League(name="League One")
    owner = models.User(
        username="owner-a",
        email="owner-a@test.com",
        hashed_password="hashed",
        league_id=1,
    )
    db.add_all([league, owner])
    db.commit()

    async def deny_commissioner():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Commissioner privileges required.",
        )

    app.dependency_overrides[check_is_commissioner] = deny_commissioner

    response = client.delete(f"/leagues/{league.id}/members/{owner.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied. Commissioner privileges required."


def test_remove_member_succeeds_for_commissioner_and_unassigns_owner(client, api_db):
    db, SessionLocal = api_db

    league = models.League(name="League Two")
    db.add(league)
    db.commit()
    db.refresh(league)

    commissioner = models.User(
        username="commish",
        email="commish@test.com",
        hashed_password="hashed",
        is_commissioner=True,
        league_id=league.id,
    )
    owner = models.User(
        username="owner-b",
        email="owner-b@test.com",
        hashed_password="hashed",
        league_id=league.id,
    )
    db.add_all([commissioner, owner])
    db.commit()
    db.refresh(owner)

    async def allow_commissioner():
        return commissioner

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    response = client.delete(f"/leagues/{league.id}/members/{owner.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "User removed from league."

    verify_session = SessionLocal()
    try:
        updated_owner = verify_session.query(models.User).filter(models.User.id == owner.id).first()
        assert updated_owner is not None
        assert updated_owner.league_id is None
    finally:
        verify_session.close()
