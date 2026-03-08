import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.matchups import get_matchup_detail, get_team_starters


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


def _seed_matchup_data(db_session):
    league = models.League(name="Phase1 League")
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    db_session.add(models.LeagueSettings(league_id=league.id, draft_year=2026))

    home = models.User(username="home", hashed_password="pw", league_id=league.id)
    away = models.User(username="away", hashed_password="pw", league_id=league.id)
    db_session.add_all([home, away])
    db_session.commit()
    db_session.refresh(home)
    db_session.refresh(away)

    home_qb = models.Player(name="Home QB", position="QB", nfl_team="AAA")
    away_wr = models.Player(name="Away WR", position="WR", nfl_team="BBB")
    db_session.add_all([home_qb, away_wr])
    db_session.commit()
    db_session.refresh(home_qb)
    db_session.refresh(away_wr)

    db_session.add_all(
        [
            models.DraftPick(
                owner_id=home.id,
                player_id=home_qb.id,
                league_id=league.id,
                current_status="STARTER",
            ),
            models.DraftPick(
                owner_id=away.id,
                player_id=away_wr.id,
                league_id=league.id,
                current_status="STARTER",
            ),
        ]
    )

    db_session.add_all(
        [
            models.ScoringRule(
                league_id=league.id,
                season_year=2026,
                category="passing",
                event_name="passing_yards",
                range_min=0,
                range_max=9999,
                point_value=0.04,
                calculation_type="per_unit",
                applicable_positions=["QB"],
                is_active=True,
            ),
            models.ScoringRule(
                league_id=league.id,
                season_year=2026,
                category="receiving",
                event_name="receptions",
                range_min=0,
                range_max=999,
                point_value=1.0,
                calculation_type="ppr",
                applicable_positions=["WR"],
                is_active=True,
            ),
        ]
    )

    db_session.add_all(
        [
            models.PlayerWeeklyStat(
                player_id=home_qb.id,
                season=2026,
                week=3,
                stats={"passing_yards": 250},
                fantasy_points=18.0,
                source="test",
            ),
            models.PlayerWeeklyStat(
                player_id=away_wr.id,
                season=2026,
                week=3,
                stats={"receptions": 6},
                fantasy_points=9.0,
                source="test",
            ),
        ]
    )

    matchup = models.Matchup(
        week=3,
        league_id=league.id,
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=0,
        away_score=0,
    )
    db_session.add(matchup)
    db_session.commit()
    db_session.refresh(matchup)

    return {
        "league_id": league.id,
        "home_id": home.id,
        "away_id": away.id,
        "matchup_id": matchup.id,
    }


def test_get_team_starters_uses_scoring_service_points(db_session):
    seeded = _seed_matchup_data(db_session)

    home_starters = get_team_starters(
        db_session,
        seeded["home_id"],
        league_id=seeded["league_id"],
        season=2026,
        week=3,
    )
    away_starters = get_team_starters(
        db_session,
        seeded["away_id"],
        league_id=seeded["league_id"],
        season=2026,
        week=3,
    )

    assert len(home_starters) == 1
    assert len(away_starters) == 1

    # 250 passing yards * 0.04
    assert home_starters[0].projected == pytest.approx(10.0)
    # actual comes from weekly stat fantasy_points when available
    assert home_starters[0].actual == pytest.approx(18.0)

    # 6 receptions * 1.0
    assert away_starters[0].projected == pytest.approx(6.0)
    assert away_starters[0].actual == pytest.approx(9.0)


def test_get_matchup_detail_aggregates_projected_from_scored_starters(db_session):
    seeded = _seed_matchup_data(db_session)

    payload = get_matchup_detail(seeded["matchup_id"], db_session)

    assert payload.home_projected == pytest.approx(10.0)
    assert payload.away_projected == pytest.approx(6.0)
    assert payload.home_roster[0].projected == pytest.approx(10.0)
    assert payload.away_roster[0].projected == pytest.approx(6.0)
