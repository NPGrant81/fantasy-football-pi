import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.trades import propose_trade, approve_trade, reject_trade, submit_trade_v2
from backend.routers.trades import TradeSubmissionCreate, TradeAssetCreate
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
    # owner1 has already designated p1 as a keeper
    k = models.Keeper(league_id=league.id, owner_id=owner1.id, player_id=p1.id, season=2026, keep_cost=10, status="pending")
    db.add(k)
    db.commit()

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
    tr = db.get(models.TradeProposal, tid)
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
    tr2 = db.get(models.TradeProposal, tid)
    assert tr2.status == "APPROVED"
    # budgets adjusted
    assert owner1.future_draft_budget == 20 - 10 + 5
    assert owner2.future_draft_budget == 15 - 5 + 10
    # players swapped
    p1pick = db.query(models.DraftPick).filter(models.DraftPick.player_id == p1.id).first()
    assert p1pick.owner_id == owner2.id
    p2pick = db.query(models.DraftPick).filter(models.DraftPick.player_id == p2.id).first()
    assert p2pick.owner_id == owner1.id
    # keeper entry should also move
    kentry = db.query(models.Keeper).filter(models.Keeper.player_id == p1.id).first()
    assert kentry.owner_id == owner2.id


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


def test_trade_proposal_respects_commissioner_trade_deadline():
    db = setup_db()
    league = make_league(db)
    db.add(
        models.LeagueSettings(
            league_id=league.id,
            trade_deadline="2000-01-01T00:00:00Z",
            future_draft_cap=25,
        )
    )
    db.commit()

    owner1 = make_user(db, league, "deadline-owner-1", budget=20)
    owner2 = make_user(db, league, "deadline-owner-2", budget=20)
    p1 = make_player(db, "Deadline A")
    p2 = make_player(db, "Deadline B")
    make_pick(db, owner1, p1)
    make_pick(db, owner2, p2)

    class CU:
        def __init__(self, user):
            self.id = user.id
            self.league_id = user.league_id
            self.future_draft_budget = user.future_draft_budget

    payload = type("P", (), {})()
    payload.to_user_id = owner2.id
    payload.offered_player_id = p1.id
    payload.requested_player_id = p2.id
    payload.offered_dollars = 0
    payload.requested_dollars = 0
    payload.note = "after deadline"

    with pytest.raises(HTTPException) as exc:
        propose_trade(payload, db=db, current_user=CU(owner1))

    assert exc.value.status_code == 400
    assert "Trade proposals are closed" in str(exc.value.detail)


# ==== INTEGRATION TESTS FOR SUBMIT_TRADE_V2 (#349) ====


class _SubmitCU:
    """Minimal mock CurrentUser for submit_trade_v2 tests."""
    def __init__(self, user):
        self.id = user.id
        self.league_id = user.league_id



def test_submit_trade_v2_creates_pending_trade_with_events():
    """Trade created with Pending status and SUBMITTED event recorded."""
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id, roster_size=15))
    db.commit()

    team_a = make_user(db, league, "team_a", budget=50)
    team_b = make_user(db, league, "team_b", budget=50)
    p1 = make_player(db, "Player A")
    p2 = make_player(db, "Player B")
    make_pick(db, team_a, p1)
    make_pick(db, team_b, p2)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=p1.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=p2.id)],
        proposal_note="Fair deal",
    )

    result = submit_trade_v2(league.id, payload, db=db, current_user=_SubmitCU(team_a))
    assert result["status"] == "PENDING"
    assert "trade_id" in result

    # Verify trade exists with correct status
    trade = db.get(models.Trade, result["trade_id"])
    assert trade is not None
    assert trade.status == "PENDING"
    assert trade.league_id == league.id
    assert trade.team_a_id == team_a.id
    assert trade.team_b_id == team_b.id

    # Verify assets were created
    assert len(trade.assets) == 2
    assets_by_side = {asset.asset_side: asset for asset in trade.assets}
    assert assets_by_side["A"].asset_type == "PLAYER"
    assert assets_by_side["A"].player_id == p1.id
    assert assets_by_side["B"].asset_type == "PLAYER"
    assert assets_by_side["B"].player_id == p2.id

    # Verify SUBMITTED event was recorded
    assert len(trade.events) >= 1
    submitted_event = next((e for e in trade.events if e.event_type == "SUBMITTED"), None)
    assert submitted_event is not None
    assert submitted_event.actor_user_id == team_a.id
    assert submitted_event.metadata_json.get("proposal_note") == "Fair deal"


def test_submit_trade_v2_rejects_unauthorized_user():
    """Unauthorized access rejected when user not in either team."""
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id))
    db.commit()

    team_a = make_user(db, league, "team_a", budget=50)
    team_b = make_user(db, league, "team_b", budget=50)
    outsider = make_user(db, league, "outsider", budget=50)
    p1 = make_player(db, "P1")
    p2 = make_player(db, "P2")
    make_pick(db, team_a, p1)
    make_pick(db, team_b, p2)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=p1.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=p2.id)],
    )

    with pytest.raises(HTTPException) as exc:
        submit_trade_v2(league.id, payload, db=db, current_user=_SubmitCU(outsider))
    assert exc.value.status_code == 403


def test_submit_trade_v2_requires_team_a_submission():
    """Trade must be submitted by team_a user."""
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id))
    db.commit()

    team_a = make_user(db, league, "team_a", budget=50)
    team_b = make_user(db, league, "team_b", budget=50)
    p1 = make_player(db, "P1")
    p2 = make_player(db, "P2")
    make_pick(db, team_a, p1)
    make_pick(db, team_b, p2)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=p1.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=p2.id)],
    )

    # Team B trying to submit as team A should fail
    with pytest.raises(HTTPException) as exc:
        submit_trade_v2(league.id, payload, db=db, current_user=_SubmitCU(team_b))
    assert exc.value.status_code == 403
    assert "team_a_id" in str(exc.value.detail).lower() or "team A" in str(exc.value.detail)


def test_submit_trade_v2_rejects_same_team_both_sides():
    """Rejects when same team on both sides."""
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id))
    db.commit()

    team = make_user(db, league, "team", budget=50)
    p1 = make_player(db, "P1")
    p2 = make_player(db, "P2")
    make_pick(db, team, p1)
    make_pick(db, team, p2)

    payload = TradeSubmissionCreate(
        team_a_id=team.id,
        team_b_id=team.id,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=p1.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=p2.id)],
    )

    with pytest.raises(HTTPException) as exc:
        submit_trade_v2(league.id, payload, db=db, current_user=_SubmitCU(team))
    assert exc.value.status_code == 400
    assert "different" in str(exc.value.detail).lower()


def test_submit_trade_v2_rejects_player_not_owned():
    """Rejects when team doesn't own offered player."""
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id))
    db.commit()

    team_a = make_user(db, league, "team_a", budget=50)
    team_b = make_user(db, league, "team_b", budget=50)
    p_owned = make_player(db, "Owned")
    p_not_owned = make_player(db, "NotOwned")
    p_other = make_player(db, "Other")
    make_pick(db, team_a, p_owned)
    make_pick(db, team_b, p_other)
    # p_not_owned is not owned by anyone

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=p_not_owned.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=p_other.id)],
    )

    with pytest.raises(HTTPException) as exc:
        submit_trade_v2(league.id, payload, db=db, current_user=_SubmitCU(team_a))
    assert exc.value.status_code == 400
    assert "does not own" in str(exc.value.detail).lower()


def test_submit_trade_v2_rejects_invalid_validation():
    """Rejects trade that fails validation (e.g., insufficient budget)."""
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id))
    db.commit()

    team_a = make_user(db, league, "team_a", budget=10)  # Low budget
    team_b = make_user(db, league, "team_b", budget=50)
    p1 = make_player(db, "P1")
    p2 = make_player(db, "P2")
    make_pick(db, team_a, p1)
    make_pick(db, team_b, p2)

    # Try to trade 50 dollars from team_a with only 10 available
    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[TradeAssetCreate(asset_type="DRAFT_DOLLARS", amount=50)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=p2.id)],
    )

    with pytest.raises(HTTPException) as exc:
        submit_trade_v2(league.id, payload, db=db, current_user=_SubmitCU(team_a))
    assert exc.value.status_code == 400
    assert "draft dollar" in str(exc.value.detail).lower() or "cannot trade" in str(exc.value.detail).lower()


def test_submit_trade_v2_multi_asset_trade():
    """Successfully submit multi-asset trade (players + picks + dollars)."""
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id, roster_size=15))
    db.commit()

    team_a = make_user(db, league, "team_a", budget=100)
    team_b = make_user(db, league, "team_b", budget=100)
    p1 = make_player(db, "P1")
    p2 = make_player(db, "P2")
    p3 = make_player(db, "P3")
    pick_a = make_pick(db, team_a, p1)
    pick_b = make_pick(db, team_b, p2)
    make_pick(db, team_a, p3)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[
            TradeAssetCreate(asset_type="PLAYER", player_id=p1.id),
            TradeAssetCreate(asset_type="DRAFT_DOLLARS", amount=25),
        ],
        assets_from_b=[
            TradeAssetCreate(asset_type="PLAYER", player_id=p2.id),
            TradeAssetCreate(asset_type="DRAFT_PICK", draft_pick_id=pick_b.id, season_year=2027),
        ],
    )

    result = submit_trade_v2(league.id, payload, db=db, current_user=_SubmitCU(team_a))
    assert result["status"] == "PENDING"

    trade = db.get(models.Trade, result["trade_id"])
    assert len(trade.assets) == 4
    # 2 from team_a, 2 from team_b
    a_assets = [a for a in trade.assets if a.asset_side == "A"]
    b_assets = [a for a in trade.assets if a.asset_side == "B"]
    assert len(a_assets) == 2
    assert len(b_assets) == 2

    # Verify asset types
    a_types = {a.asset_type for a in a_assets}
    assert "PLAYER" in a_types
    assert "DRAFT_DOLLARS" in a_types
    b_types = {a.asset_type for a in b_assets}
    assert "PLAYER" in b_types
    assert "DRAFT_PICK" in b_types


def test_submit_trade_v2_respects_commissioner_deadline():
    """Rejects trade when past commissioner-set deadline."""
    db = setup_db()
    league = make_league(db)
    # Set trade deadline to past
    db.add(
        models.LeagueSettings(
            league_id=league.id,
            trade_deadline="2000-01-01T00:00:00Z",
            roster_size=15,
        )
    )
    db.commit()

    team_a = make_user(db, league, "team_a", budget=50)
    team_b = make_user(db, league, "team_b", budget=50)
    p1 = make_player(db, "P1")
    p2 = make_player(db, "P2")
    make_pick(db, team_a, p1)
    make_pick(db, team_b, p2)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=p1.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=p2.id)],
    )

    with pytest.raises(HTTPException) as exc:
        submit_trade_v2(league.id, payload, db=db, current_user=_SubmitCU(team_a))
    assert exc.value.status_code == 400
    assert "closed" in str(exc.value.detail).lower() or "trade" in str(exc.value.detail).lower()


def test_submit_trade_v2_league_access_control():
    """Rejects when user's league doesn't match requested league."""
    db = setup_db()
    league1 = make_league(db, "L1")
    league2 = make_league(db, "L2")
    db.add(models.LeagueSettings(league_id=league1.id))
    db.add(models.LeagueSettings(league_id=league2.id))
    db.commit()

    team_a = make_user(db, league1, "team_a", budget=50)
    # User belongs to league1 but tries to submit trade in league2
    p1 = make_player(db, "P1")
    p2 = make_player(db, "P2")
    make_pick(db, team_a, p1)
    make_pick(db, team_a, p2)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_a.id + 1000,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=p1.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=p2.id)],
    )

    with pytest.raises(HTTPException) as exc:
        submit_trade_v2(league2.id, payload, db=db, current_user=_SubmitCU(team_a))
    assert exc.value.status_code == 403
