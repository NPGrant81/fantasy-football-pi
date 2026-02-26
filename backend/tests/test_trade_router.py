import sys
from pathlib import Path
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.trades import propose_trade, approve_trade, reject_trade
from backend.services.transaction_service import get_acquisition_method
from fastapi import HTTPException


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def make_league(db, name="L"):
    l = models.League(name=name)
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def make_user(db, league, username="u", is_comm=False, budget=0):
    u = models.User(username=username, hashed_password="pw", league_id=league.id, future_draft_budget=budget)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def make_player(db, name):
    p = models.Player(name=name, position="RB", nfl_team="AAA")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def make_pick(db, owner, player):
    pick = models.DraftPick(owner_id=owner.id, player_id=player.id, league_id=owner.league_id)
    db.add(pick)
    db.commit()
    db.refresh(pick)
    return pick


def test_trade_proposal_and_approval():
    db = setup_db()
    league = make_league(db)
    # set league cap
    ls = models.LeagueSettings(league_id=league.id, future_draft_cap=25)
    db.add(ls)
    db.commit()

    owner1 = make_user(db, league, "owner1", budget=20)
    owner2 = make_user(db, league, "owner2", budget=15)
    p1 = make_player(db, "Alice")
    p2 = make_player(db, "Bob")
    make_pick(db, owner1, p1)
    make_pick(db, owner2, p2)

    # create a fake current_user object with required attrs
    class CU:
        def __init__(self, user):
            self.id = user.id
            self.league_id = user.league_id
            self.future_draft_budget = user.future_draft_budget
    cu1 = CU(owner1)

    payload = type("P", (), {})()
    payload.to_user_id = owner2.id
    payload.offered_player_id = p1.id
    payload.requested_player_id = p2.id
    payload.offered_dollars = 10
    payload.requested_dollars = 5
    payload.note = ""

    result = propose_trade(payload, db=db, current_user=cu1)
    assert "trade_id" in result
    tid = result["trade_id"]
    # verify trade record exists
    tr = db.query(models.TradeProposal).get(tid)
    assert tr.offered_dollars == 10
    assert tr.requested_dollars == 5
    assert tr.status == "PENDING"

    # approval by commissioner
    comm = make_user(db, league, "comm", is_comm=True, budget=0)
    class CUC:
        def __init__(self, user):
            self.id = user.id
            self.league_id = user.league_id
    cuc = CUC(comm)
    res = approve_trade(trade_id=tid, db=db, current_user=cuc)
    assert res["message"] == "Trade approved"
    tr2 = db.query(models.TradeProposal).get(tid)
    assert tr2.status == "APPROVED"
    # budgets adjusted
    assert owner1.future_draft_budget == 20 - 10 + 5
    assert owner2.future_draft_budget == 15 - 5 + 10
    # players swapped
    p1pick = db.query(models.DraftPick).filter(models.DraftPick.player_id == p1.id).first()
    assert p1pick.owner_id == owner2.id
    p2pick = db.query(models.DraftPick).filter(models.DraftPick.player_id == p2.id).first()
    assert p2pick.owner_id == owner1.id


def test_trade_proposal_validation():
    db = setup_db()
    league = make_league(db)
    owner1 = make_user(db, league, "o1", budget=5)
    owner2 = make_user(db, league, "o2", budget=5)
    p1 = make_player(db, "A")
    make_pick(db, owner1, p1)
    class CU:
        def __init__(self, user):
            self.id = user.id
            self.league_id = user.league_id
            self.future_draft_budget = user.future_draft_budget
    cu = CU(owner1)
    payload = type("P", (), {})()
    payload.to_user_id = owner2.id
    payload.offered_player_id = p1.id
    payload.requested_player_id = p1.id
    payload.offered_dollars = 10
    payload.requested_dollars = 0
    payload.note = None
    with pytest.raises(HTTPException):
        propose_trade(payload, db=db, current_user=cu)
