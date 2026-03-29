import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.news import (
    NewsIngestRequest,
    global_news,
    ingest_news,
    sentiment_shifts,
    sentiment_trends,
    team_news,
)


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return SessionLocal()


def make_league(db, name="L"):
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
    player = models.Player(name=name, position="WR", nfl_team="KC")
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def make_pick(db, league, owner, player, amount=10, ts="2026-03-29T10:00:00Z"):
    pick = models.DraftPick(
        league_id=league.id,
        owner_id=owner.id,
        player_id=player.id,
        amount=amount,
        timestamp=ts,
    )
    db.add(pick)
    db.commit()
    db.refresh(pick)
    return pick


def test_ingest_and_global_team_news_filters():
    db = setup_db()
    league = make_league(db)
    owner_a = make_user(db, league, "alpha")
    owner_b = make_user(db, league, "beta")
    player_a = make_player(db, "Ja'Marr Chase")
    player_b = make_player(db, "Josh Allen")

    make_pick(db, league, owner_a, player_a, amount=22)
    make_pick(db, league, owner_b, player_b, amount=30)

    result = ingest_news(
        NewsIngestRequest(
            league_id=league.id,
            include_draft_activity=True,
            include_external_sources=False,
        ),
        db=db,
    )

    assert result["inserted"] >= 2

    all_items = global_news(league_id=league.id, player_id=None, since=None, limit=20, db=db)
    assert len(all_items) >= 2

    team_items = team_news(team_id=owner_a.id, league_id=league.id, since=None, limit=20, db=db)
    titles = [item.title for item in team_items]
    assert any("Ja'Marr Chase" in title for title in titles)
    assert not any("Josh Allen" in title for title in titles)


def test_sentiment_trends_and_shifts_endpoints():
    db = setup_db()
    league = make_league(db)
    owner = make_user(db, league, "alpha")
    player = make_player(db, "Ja'Marr Chase")

    make_pick(db, league, owner, player, amount=12, ts="2026-03-29T10:00:00Z")

    ingest_news(
        NewsIngestRequest(
            league_id=league.id,
            include_draft_activity=True,
            include_external_sources=False,
        ),
        db=db,
    )

    trend_rows = sentiment_trends(league_id=league.id, player_id=player.id, window_hours=None, db=db)
    assert len(trend_rows) >= 1
    assert all(row.player_id == player.id for row in trend_rows)

    shift_rows = sentiment_shifts(league_id=league.id, min_delta=0.0, db=db)
    assert isinstance(shift_rows, list)
