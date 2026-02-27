import sys
from pathlib import Path
from fastapi.testclient import TestClient

import pytest
from sqlalchemy import create_engine

from backend.main import app
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.waivers import list_waiver_claims


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_user(db, league, username="u", is_comm=False):
    user = models.User(
        username=username,
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=is_comm,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_player(db, name="P"):  # simple helper
    p = models.Player(name=name, position="RB", nfl_team="ABC")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_list_waiver_claims_only_league(db_session):
    league1 = models.League(name="L1")
    league2 = models.League(name="L2")
    db_session.add_all([league1, league2])
    db_session.commit()

    comm1 = make_user(db_session, league1, username="comm1", is_comm=True)
    user1 = make_user(db_session, league1, username="user1")
    user2 = make_user(db_session, league2, username="user2")

    p1 = make_player(db_session, "Alice")
    p2 = make_player(db_session, "Bob")

    claim1 = models.WaiverClaim(
        league_id=league1.id,
        user_id=user1.id,
        player_id=p1.id,
        bid_amount=10,
        status="PENDING",
    )
    claim2 = models.WaiverClaim(
        league_id=league2.id,
        user_id=user2.id,
        player_id=p2.id,
        bid_amount=5,
        status="PENDING",
    )
    db_session.add_all([claim1, claim2])
    db_session.commit()

    # call the router function as if commissioner from league1
    results = list_waiver_claims(db=db_session, current_user=comm1)
    assert isinstance(results, list)
    assert len(results) == 1
    rec = results[0]
    assert rec["league_id"] == league1.id
    assert rec["user_id"] == user1.id
    assert rec["player_name"] == "Alice"


def test_list_waiver_claims_requires_commissioner(db_session):
    league = models.League(name="LX")
    db_session.add(league)
    db_session.commit()
    user = make_user(db_session, league, username="user", is_comm=False)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        list_waiver_claims(db=db_session, current_user=user)
    assert exc.value.status_code == 403


def test_submit_claim_includes_team_id(monkeypatch, db_session):
    league = models.League(name="LZ")
    db_session.add(league)
    db_session.commit()
    user = make_user(db_session, league, username="uct", is_comm=False)

    # monkeypatch service to capture arguments
    called = {}
    def fake_process_claim(*args, **kwargs):
        # router will pass keywords: db, user, player_id, bid, drop_id, team_id
        user_arg = kwargs.get('user') or (args[1] if len(args) > 1 else None)
        called['user_id'] = user_arg.id if user_arg else None
        called['team_id'] = kwargs.get('team_id')
        return models.DraftPick(id=1, owner_id=user_arg.id, player_id=kwargs.get('player_id'), amount=kwargs.get('bid'))

    monkeypatch.setattr('backend.routers.waivers.waiver_service',
                        type('X', (), {'process_claim': fake_process_claim}))

    # override current user dependency using actual function reference
    from backend.routers import waivers as waiver_module
    def fake_current():
        return user
    app.dependency_overrides[waiver_module.get_current_user] = fake_current

    payload = {'player_id': 5, 'bid_amount': 20, 'team_id': 99}
    client = TestClient(app)
    resp = client.post('/waivers/claim', json=payload)
    assert resp.status_code == 200
    assert called['user_id'] == user.id
    assert called['team_id'] == 99

    app.dependency_overrides.clear()
