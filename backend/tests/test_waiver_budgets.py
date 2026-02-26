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
# client fixture from backend/conftest supplies TestClient


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


@pytest.fixture(autouse=True)
def override_db(api_db):
    db, _ = api_db
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def test_get_waiver_budgets_empty(client):
    # league must exist first
    league = models.League(name="Test League")
    db = client.app.dependency_overrides[get_db]().__next__()
    db.add(league)
    db.commit()

    res = client.get(f"/leagues/{league.id}/waiver-budgets")
    assert res.status_code == 200
    assert res.json() == []


def test_get_waiver_budgets_with_record(client):
    league = models.League(name="Test League2")
    user = models.User(username="bob", hashed_password="x")
    db = client.app.dependency_overrides[get_db]().__next__()
    db.add_all([league, user])
    db.commit()

    budget = models.WaiverBudget(
        league_id=league.id,
        owner_id=user.id,
        starting_budget=100,
        remaining_budget=80,
        spent_budget=20,
    )
    db.add(budget)
    db.commit()

    res = client.get(f"/leagues/{league.id}/waiver-budgets")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list) and len(data) == 1
    entry = data[0]
    assert entry["owner_id"] == user.id
    assert entry["remaining_budget"] == 80
