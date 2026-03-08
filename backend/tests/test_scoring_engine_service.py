import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.services.scoring_service import calculate_points_for_stats, recalculate_league_week_scores


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


def test_calculate_points_for_stats_handles_decimal_and_ppr_rules():
    rules = [
        models.ScoringRule(
            league_id=1,
            category="passing",
            event_name="passing_yards",
            range_min=0,
            range_max=9999,
            point_value=0.04,
            calculation_type="per_unit",
            applicable_positions=["QB"],
        ),
        models.ScoringRule(
            league_id=1,
            category="receiving",
            event_name="receptions",
            range_min=0,
            range_max=999,
            point_value=0.5,
            calculation_type="half_ppr",
            applicable_positions=["RB", "WR", "TE"],
        ),
        models.ScoringRule(
            league_id=1,
            category="passing",
            event_name="passing_tds",
            range_min=1,
            range_max=999,
            point_value=4.0,
            calculation_type="per_unit",
            applicable_positions=["QB"],
        ),
    ]

    total, breakdown = calculate_points_for_stats(
        stats={"passing_yards": 250, "passing_tds": 2, "receptions": 6},
        position="QB",
        rules=rules,
    )

    # QB should receive passing yards + passing TDs but not half-PPR receptions.
    assert total == pytest.approx(18.0)
    assert len(breakdown) == 2
    assert {item.event_name for item in breakdown} == {"passing_yards", "passing_tds"}


def test_recalculate_league_week_scores_updates_matchup_totals(db_session):
    league = models.League(name="Scoring Engine League")
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    home = models.User(username="home-owner", hashed_password="pw", league_id=league.id)
    away = models.User(username="away-owner", hashed_password="pw", league_id=league.id)
    db_session.add_all([home, away])
    db_session.commit()
    db_session.refresh(home)
    db_session.refresh(away)

    qb_home = models.Player(name="Home QB", position="QB", nfl_team="AAA")
    wr_away = models.Player(name="Away WR", position="WR", nfl_team="BBB")
    db_session.add_all([qb_home, wr_away])
    db_session.commit()
    db_session.refresh(qb_home)
    db_session.refresh(wr_away)

    db_session.add_all(
        [
            models.DraftPick(owner_id=home.id, player_id=qb_home.id, current_status="STARTER"),
            models.DraftPick(owner_id=away.id, player_id=wr_away.id, current_status="STARTER"),
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
                applicable_positions=["WR", "TE", "RB"],
                is_active=True,
            ),
            models.ScoringRule(
                league_id=league.id,
                season_year=2026,
                category="receiving",
                event_name="receiving_tds",
                range_min=1,
                range_max=999,
                point_value=6.0,
                calculation_type="per_unit",
                applicable_positions=["WR", "TE", "RB"],
                is_active=True,
            ),
        ]
    )

    db_session.add_all(
        [
            models.PlayerWeeklyStat(
                player_id=qb_home.id,
                season=2026,
                week=3,
                stats={"passing_yards": 300},
                fantasy_points=0,
                source="test",
            ),
            models.PlayerWeeklyStat(
                player_id=wr_away.id,
                season=2026,
                week=3,
                stats={"receptions": 8, "receiving_tds": 1},
                fantasy_points=0,
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

    results = recalculate_league_week_scores(
        db_session,
        league_id=league.id,
        week=3,
        season=2026,
        season_year=2026,
    )
    db_session.commit()
    db_session.refresh(matchup)

    assert len(results) == 1
    assert matchup.home_score == pytest.approx(12.0)
    assert matchup.away_score == pytest.approx(14.0)
    assert matchup.is_completed is True
    assert matchup.game_status == "FINAL"
