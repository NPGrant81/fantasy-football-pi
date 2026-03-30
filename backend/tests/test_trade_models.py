import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return testing_session_local()


def make_league(db, name="TradeLeague"):
    league = models.League(name=name)
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def make_user(db, league, username):
    user = models.User(username=username, hashed_password="pw", league_id=league.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_player(db, name):
    player = models.Player(name=name, position="RB", nfl_team="AAA")
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def make_pick(db, league_id, owner_id, player_id):
    pick = models.DraftPick(league_id=league_id, owner_id=owner_id, player_id=player_id)
    db.add(pick)
    db.commit()
    db.refresh(pick)
    return pick


def test_trade_and_trade_assets_persist_with_relationships():
    db = setup_db()
    league = make_league(db)
    team_a = make_user(db, league, "team-a")
    team_b = make_user(db, league, "team-b")

    player = make_player(db, "Sample Player")
    pick = make_pick(db, league.id, team_a.id, player.id)

    trade = models.Trade(
        league_id=league.id,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        created_by_user_id=team_a.id,
        status="PENDING",
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    assets = [
        models.TradeAsset(
            trade_id=trade.id,
            asset_side="A",
            asset_type="PLAYER",
            player_id=player.id,
        ),
        models.TradeAsset(
            trade_id=trade.id,
            asset_side="A",
            asset_type="DRAFT_PICK",
            draft_pick_id=pick.id,
            season_year=2027,
        ),
        models.TradeAsset(
            trade_id=trade.id,
            asset_side="B",
            asset_type="DRAFT_DOLLARS",
            amount=15,
        ),
    ]
    db.add_all(assets)
    db.commit()

    saved_trade = db.get(models.Trade, trade.id)
    assert saved_trade is not None
    assert saved_trade.status == "PENDING"
    assert saved_trade.league_id == league.id
    assert len(saved_trade.assets) == 3

    by_type = {asset.asset_type: asset for asset in saved_trade.assets}
    assert by_type["PLAYER"].player_id == player.id
    assert by_type["DRAFT_PICK"].draft_pick_id == pick.id
    assert float(by_type["DRAFT_DOLLARS"].amount or 0) == 15.0
