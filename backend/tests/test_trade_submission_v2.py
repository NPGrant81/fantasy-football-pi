import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
import backend.services.notifications as notifications_module
from backend.routers.trades import submit_trade_v2, TradeSubmissionCreate, TradeAssetCreate
from fastapi import HTTPException


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return testing_session_local()


def make_league(db, name="LeagueV2"):
    league = models.League(name=name, current_season=2026)
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def make_user(db, league, username, budget=0):
    user = models.User(
        username=username,
        hashed_password="pw",
        league_id=league.id,
        future_draft_budget=budget,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_player(db, name, position="RB"):
    player = models.Player(name=name, position=position, nfl_team="AAA")
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def make_pick(db, league_id, owner_id, player_id=None, year=2027):
    pick = models.DraftPick(league_id=league_id, owner_id=owner_id, player_id=player_id, year=year)
    db.add(pick)
    db.commit()
    db.refresh(pick)
    return pick


class CU:
    def __init__(self, user):
        self.id = user.id
        self.league_id = user.league_id
        self.future_draft_budget = user.future_draft_budget


def test_submit_trade_v2_creates_pending_trade_and_assets(monkeypatch):
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id, roster_size=16, trade_deadline=None))
    db.commit()

    team_a = make_user(db, league, "team-a", budget=30)
    team_b = make_user(db, league, "team-b", budget=20)
    commissioner = make_user(db, league, "commish", budget=0)
    commissioner.is_commissioner = True
    db.commit()

    sent = []
    monkeypatch.setattr(
        notifications_module.NotifyService,
        "send_transactional_email",
        lambda user_id, template_id, context: sent.append((user_id, template_id, context)),
    )

    player_a = make_player(db, "A Player", position="RB")
    player_b = make_player(db, "B Player", position="WR")

    make_pick(db, league.id, team_a.id, player_a.id)
    make_pick(db, league.id, team_b.id, player_b.id)
    pick_a = make_pick(db, league.id, team_a.id, None, year=2027)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[
            TradeAssetCreate(asset_type="PLAYER", player_id=player_a.id),
            TradeAssetCreate(asset_type="DRAFT_PICK", draft_pick_id=pick_a.id, season_year=2027),
        ],
        assets_from_b=[
            TradeAssetCreate(asset_type="PLAYER", player_id=player_b.id),
            TradeAssetCreate(asset_type="DRAFT_DOLLARS", amount=10),
        ],
    )

    result = submit_trade_v2(league.id, payload, db=db, current_user=CU(team_a))

    assert result["status"] == "PENDING"
    trade_id = result["trade_id"]

    saved_trade = db.get(models.Trade, trade_id)
    assert saved_trade is not None
    assert saved_trade.team_a_id == team_a.id
    assert saved_trade.team_b_id == team_b.id

    assets = db.query(models.TradeAsset).filter(models.TradeAsset.trade_id == trade_id).all()
    assert len(assets) == 4

    events = (
        db.query(models.TradeEvent)
        .filter(models.TradeEvent.trade_id == trade_id)
        .order_by(models.TradeEvent.id.asc())
        .all()
    )
    assert len(events) == 1
    assert events[0].event_type == "SUBMITTED"
    assert events[0].actor_user_id == team_a.id

    recipient_ids = {user_id for user_id, template_id, _ in sent if template_id == "trade_submitted_pending_review"}
    assert recipient_ids == {team_b.id, commissioner.id}


def test_submit_trade_v2_requires_current_user_on_trade_team():
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id, roster_size=16, trade_deadline=None))
    db.commit()

    team_a = make_user(db, league, "team-a", budget=30)
    team_b = make_user(db, league, "team-b", budget=20)
    outsider = make_user(db, league, "outsider", budget=50)

    player_a = make_player(db, "A Player", position="RB")
    player_b = make_player(db, "B Player", position="WR")
    make_pick(db, league.id, team_a.id, player_a.id)
    make_pick(db, league.id, team_b.id, player_b.id)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=player_a.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=player_b.id)],
    )

    with pytest.raises(HTTPException) as exc:
        submit_trade_v2(league.id, payload, db=db, current_user=CU(outsider))

    assert exc.value.status_code == 403


def test_submit_trade_v2_rejects_player_not_owned_by_offering_team():
    db = setup_db()
    league = make_league(db)
    db.add(models.LeagueSettings(league_id=league.id, roster_size=16, trade_deadline=None))
    db.commit()

    team_a = make_user(db, league, "team-a-ownership", budget=30)
    team_b = make_user(db, league, "team-b-ownership", budget=20)

    player_a = make_player(db, "A Ownership Player", position="RB")
    player_b = make_player(db, "B Ownership Player", position="WR")
    make_pick(db, league.id, team_a.id, player_a.id)
    make_pick(db, league.id, team_b.id, player_b.id)

    payload = TradeSubmissionCreate(
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        assets_from_a=[TradeAssetCreate(asset_type="PLAYER", player_id=player_b.id)],
        assets_from_b=[TradeAssetCreate(asset_type="PLAYER", player_id=player_a.id)],
    )

    with pytest.raises(HTTPException) as exc:
        submit_trade_v2(league.id, payload, db=db, current_user=CU(team_a))

    assert exc.value.status_code == 400
    assert "does not own player" in str(exc.value.detail)
