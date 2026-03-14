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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_db(api_db):
    def override_get_db():
        try:
            yield api_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def test_owner_can_view_own_ledger_statement(client, api_db):
    league = models.League(name="Ledger League")
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)

    owner = models.User(
        username="owner1",
        email="owner1@test.com",
        hashed_password="hashed",
        league_id=league.id,
        is_commissioner=False,
    )
    other_owner = models.User(
        username="owner2",
        email="owner2@test.com",
        hashed_password="hashed",
        league_id=league.id,
        is_commissioner=False,
    )
    api_db.add_all([owner, other_owner])
    api_db.commit()
    api_db.refresh(owner)
    api_db.refresh(other_owner)

    api_db.add_all(
        [
            models.EconomicLedger(
                league_id=league.id,
                season_year=2026,
                currency_type="FAAB",
                amount=25,
                to_owner_id=owner.id,
                transaction_type="INITIAL_BUDGET",
                notes="credit",
            ),
            models.EconomicLedger(
                league_id=league.id,
                season_year=2026,
                currency_type="FAAB",
                amount=7,
                from_owner_id=owner.id,
                to_owner_id=other_owner.id,
                transaction_type="WAIVER_CLAIM",
                notes="debit",
            ),
        ]
    )
    api_db.commit()

    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        res = client.get(f"/leagues/{league.id}/ledger/statement?currency_type=FAAB")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    body = res.json()
    assert body["owner_id"] == owner.id
    assert body["balance"] == 18
    assert [entry["direction"].lower() for entry in body["entries"]] == ["debit", "credit"]


def test_non_commissioner_cannot_view_other_owner_statement(client, api_db):
    league = models.League(name="Ledger Permissions")
    api_db.add(league)
    api_db.commit()
    api_db.refresh(league)

    owner = models.User(
        username="owner1",
        email="owner1p@test.com",
        hashed_password="hashed",
        league_id=league.id,
        is_commissioner=False,
    )
    other_owner = models.User(
        username="owner2",
        email="owner2p@test.com",
        hashed_password="hashed",
        league_id=league.id,
        is_commissioner=False,
    )
    api_db.add_all([owner, other_owner])
    api_db.commit()
    api_db.refresh(owner)
    api_db.refresh(other_owner)

    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        res = client.get(
            f"/leagues/{league.id}/ledger/statement?owner_id={other_owner.id}"
        )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403