import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.keepers import (
    get_my_keepers,
    save_my_keepers,
    lock_my_keepers,
    remove_keeper,
    get_keeper_settings,
    update_keeper_settings,
    list_all_keepers,
    veto_owner_list,
    reset_league_keepers,
    KeeperSelectionSchema,
    KeeperSettingsUpdate,
)
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
    # also add league settings
    ls = models.LeagueSettings(league_id=l.id, draft_year=2026)
    db.add(ls)
    db.commit()
    return l


def make_player(db, name="P"):
    p = models.Player(name=name, position="RB", nfl_team="ABC")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def make_user(db, league, username="u", is_comm=False, budget=0):
    u = models.User(username=username, hashed_password="pw", league_id=league.id, future_draft_budget=budget)
    u.is_commissioner = is_comm
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


class CU:
    def __init__(self, user):
        self.id = user.id
        self.league_id = user.league_id
        self.future_draft_budget = user.future_draft_budget
        self.is_commissioner = user.is_commissioner


def test_owner_keeper_endpoints():
    db_session = setup_db()
    league = make_league(db_session)
    # ensure keeper rules exist so max_allowed reflects expected value
    db_session.add(models.KeeperRules(league_id=league.id, max_keepers=3))
    db_session.commit()
    owner = make_user(db_session, league, "owner", budget=200)
    p1 = make_player(db_session, "A")
    p2 = make_player(db_session, "B")

    current = CU(owner)
    # initial get should return empty selections
    resp = get_my_keepers(db=db_session, current_user=current)
    assert resp.selected_count == 0
    assert resp.max_allowed == 3
    assert resp.estimated_budget == 200

    # save two keepers
    req = type("R", (), {})()
    req.players = [KeeperSelectionSchema(player_id=p1.id, keep_cost=10, years_kept_count=0, status="pending", approved_by_commish=False),
                   KeeperSelectionSchema(player_id=p2.id, keep_cost=20, years_kept_count=0, status="pending", approved_by_commish=False)]
    save_my_keepers(request=req, db=db_session, current_user=current)
    resp2 = get_my_keepers(db=db_session, current_user=current)
    assert resp2.selected_count == 2
    assert resp2.estimated_budget == 170

    # lock them and verify budget deduction
    # pass the actual owner object (models.User) rather than CU stub
    lock_my_keepers(db=db_session, current_user=db_session.get(models.User, owner.id))
    # use new SQLAlchemy 2.0 style get
    owner_ref = db_session.get(models.User, owner.id)
    assert owner_ref.future_draft_budget == 170
    # after lock, effective budget matches
    resp3 = get_my_keepers(db=db_session, current_user=current)
    assert resp3.effective_budget == 170

    # remove keeper should do nothing because list locked
    remove_keeper(player_id=p1.id, db=db_session, current_user=current)
    resp4 = get_my_keepers(db=db_session, current_user=current)
    assert resp4.selected_count == 2


def test_admin_settings_and_actions():
    db_session = setup_db()
    league = make_league(db_session)
    comm = make_user(db_session, league, "comm", is_comm=True)
    other = make_user(db_session, league, "owner2")
    current_comm = CU(comm)

    # update settings - use real Pydantic schema so `.model_dump()` works
    # KeeperSettingsUpdate is defined inside the router module
    from backend.routers.keepers import KeeperSettingsUpdate

    upd = KeeperSettingsUpdate(
        max_keepers=2,
        max_years_per_player=2,
        deadline_date=datetime.utcnow() + timedelta(days=1),
        waiver_policy=True,
        trade_deadline=None,
        drafted_only=True,
        cost_type="round",
        cost_inflation=5,
    )

    update_keeper_settings(update=upd, db=db_session, current_user=current_comm)
    outs = get_keeper_settings(db=db_session, current_user=current_comm)
    assert outs.max_keepers == 2
    assert outs.cost_type == "round"
    assert outs.cost_inflation == 5

    # save some keepers for both owners
    p = make_player(db_session, "X")
    req1 = type("R", (), {})()
    req1.players = [KeeperSelectionSchema(player_id=p.id, keep_cost=5, years_kept_count=0, status="pending", approved_by_commish=False)]
    save_my_keepers(request=req1, db=db_session, current_user=CU(other))
    # list all for commissioner
    all_lists = list_all_keepers(db=db_session, current_user=current_comm)
    assert len(all_lists) == 1

    # lock owner's list and then veto via admin
    lock_my_keepers(db=db_session, current_user=db_session.get(models.User, other.id))
    veto_owner_list(owner_id=other.id, db=db_session, current_user=current_comm)
    post = get_my_keepers(db=db_session, current_user=CU(other))
    assert post.selected_count == 1  # still present but status pending again

    # reset league
    reset_league_keepers(owner_id=None, db=db_session, current_user=current_comm)
    post2 = get_my_keepers(db=db_session, current_user=CU(other))
    assert post2.selected_count == 0
