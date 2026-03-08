import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.team import LineupUpdateRequest, update_lineup
from backend.services.week_finalization_service import finalize_league_week


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


def _seed_finalization_league(db):
    league = models.League(name="FinalizeLeague")
    db.add(league)
    db.commit()
    db.refresh(league)

    home = models.User(username="home", hashed_password="pw", league_id=league.id, team_name="Home Team")
    away = models.User(username="away", hashed_password="pw", league_id=league.id, team_name="Away Team")
    db.add_all([home, away])
    db.commit()
    db.refresh(home)
    db.refresh(away)

    qb = models.Player(name="QB One", position="QB", projected_points=20)
    wr = models.Player(name="WR One", position="WR", projected_points=15)
    db.add_all([qb, wr])
    db.commit()
    db.refresh(qb)
    db.refresh(wr)

    db.add_all(
        [
            models.DraftPick(owner_id=home.id, player_id=qb.id, amount=10, session_id="TEST", year=2026, league_id=league.id, current_status="STARTER"),
            models.DraftPick(owner_id=away.id, player_id=wr.id, amount=10, session_id="TEST", year=2026, league_id=league.id, current_status="STARTER"),
            models.PlayerWeeklyStat(player_id=qb.id, season=2026, week=1, fantasy_points=24.0, stats={"fantasy_points": 24.0}, source="test"),
            models.PlayerWeeklyStat(player_id=wr.id, season=2026, week=1, fantasy_points=10.0, stats={"fantasy_points": 10.0}, source="test"),
            models.Matchup(league_id=league.id, week=1, home_team_id=home.id, away_team_id=away.id, game_status="IN_PROGRESS", is_completed=False),
        ]
    )
    db.commit()

    return league, home, away


def test_finalize_week_sets_matchups_final_and_returns_standings(db_session):
    league, home, _ = _seed_finalization_league(db_session)

    result = finalize_league_week(
        db_session,
        league_id=league.id,
        week=1,
        season=2026,
        season_year=2026,
    )
    db_session.commit()

    assert result["matchups_finalized"] == 1
    assert result["standings"][0]["owner_id"] == home.id
    assert result["standings"][0]["wins"] == 1

    matchup = db_session.query(models.Matchup).filter(models.Matchup.league_id == league.id, models.Matchup.week == 1).one()
    assert matchup.is_completed is True
    assert matchup.game_status == "FINAL"
    assert matchup.home_score == 24.0
    assert matchup.away_score == 10.0


def test_update_lineup_rejects_when_week_finalized(db_session):
    league, home, _ = _seed_finalization_league(db_session)

    finalize_league_week(
        db_session,
        league_id=league.id,
        week=1,
        season=2026,
        season_year=2026,
    )
    db_session.commit()

    payload = LineupUpdateRequest(week=1, starter_player_ids=[])
    with pytest.raises(HTTPException) as exc:
        update_lineup(payload=payload, db=db_session, current_user=home)

    assert exc.value.status_code == 400
    assert "finalized" in str(exc.value.detail).lower()
