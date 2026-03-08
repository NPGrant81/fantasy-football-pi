import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.services.scoring_service import calculate_points_for_stats, recalculate_league_week_scores, recalculate_matchup_scores


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


def test_recalculate_matchup_scores_isolates_draft_picks_by_league(db_session):
    """DraftPick rows from a different league must not bleed into recalculation."""
    league_a = models.League(name="League A")
    league_b = models.League(name="League B")
    db_session.add_all([league_a, league_b])
    db_session.commit()
    db_session.refresh(league_a)
    db_session.refresh(league_b)

    # owner belongs to league_a but also has a STARTER pick in league_b
    home = models.User(username="multi-league-home", hashed_password="pw", league_id=league_a.id)
    away = models.User(username="away-single", hashed_password="pw", league_id=league_a.id)
    db_session.add_all([home, away])
    db_session.commit()
    db_session.refresh(home)
    db_session.refresh(away)

    player_a = models.Player(name="Player A", position="QB", nfl_team="AAA")
    player_b = models.Player(name="Player B", position="QB", nfl_team="BBB")
    away_player = models.Player(name="Away Player", position="WR", nfl_team="CCC")
    db_session.add_all([player_a, player_b, away_player])
    db_session.commit()
    db_session.refresh(player_a)
    db_session.refresh(player_b)
    db_session.refresh(away_player)

    # home has a STARTER in league_a and an extra STARTER in league_b (should be excluded)
    db_session.add_all(
        [
            models.DraftPick(
                owner_id=home.id,
                player_id=player_a.id,
                league_id=league_a.id,
                current_status="STARTER",
            ),
            models.DraftPick(
                owner_id=home.id,
                player_id=player_b.id,
                league_id=league_b.id,
                current_status="STARTER",
            ),
            models.DraftPick(
                owner_id=away.id,
                player_id=away_player.id,
                league_id=league_a.id,
                current_status="STARTER",
            ),
        ]
    )

    db_session.add_all(
        [
            models.ScoringRule(
                league_id=league_a.id,
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
                league_id=league_a.id,
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
                player_id=player_a.id,
                season=2026,
                week=5,
                stats={"passing_yards": 200},
                fantasy_points=0,
                source="test",
            ),
            models.PlayerWeeklyStat(
                player_id=player_b.id,
                season=2026,
                week=5,
                stats={"passing_yards": 400},
                fantasy_points=0,
                source="test",
            ),
            models.PlayerWeeklyStat(
                player_id=away_player.id,
                season=2026,
                week=5,
                stats={"receptions": 5},
                fantasy_points=0,
                source="test",
            ),
        ]
    )

    matchup = models.Matchup(
        week=5,
        league_id=league_a.id,
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=0,
        away_score=0,
    )
    db_session.add(matchup)
    db_session.commit()
    db_session.refresh(matchup)

    recalculate_matchup_scores(db_session, matchup=matchup, season=2026, season_year=2026)
    db_session.commit()
    db_session.refresh(matchup)

    # Only player_a (league_a) should count: 200 * 0.04 = 8.0
    # player_b (league_b) must NOT be included
    assert matchup.home_score == pytest.approx(8.0)
    # away: 5 receptions * 1.0 = 5.0
    assert matchup.away_score == pytest.approx(5.0)


def test_recalculate_matchup_scores_includes_legacy_null_league_id_picks(db_session):
    """Legacy DraftPick rows with league_id=NULL must still be counted."""
    league = models.League(name="Legacy League")
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    home = models.User(username="legacy-home", hashed_password="pw", league_id=league.id)
    away = models.User(username="legacy-away", hashed_password="pw", league_id=league.id)
    db_session.add_all([home, away])
    db_session.commit()
    db_session.refresh(home)
    db_session.refresh(away)

    player_home = models.Player(name="Legacy QB", position="QB", nfl_team="AAA")
    player_away = models.Player(name="Legacy WR", position="WR", nfl_team="BBB")
    db_session.add_all([player_home, player_away])
    db_session.commit()
    db_session.refresh(player_home)
    db_session.refresh(player_away)

    # Legacy rows: league_id is NULL
    db_session.add_all(
        [
            models.DraftPick(
                owner_id=home.id,
                player_id=player_home.id,
                league_id=None,
                current_status="STARTER",
            ),
            models.DraftPick(
                owner_id=away.id,
                player_id=player_away.id,
                league_id=None,
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
                player_id=player_home.id,
                season=2026,
                week=1,
                stats={"passing_yards": 250},
                fantasy_points=0,
                source="test",
            ),
            models.PlayerWeeklyStat(
                player_id=player_away.id,
                season=2026,
                week=1,
                stats={"receptions": 7},
                fantasy_points=0,
                source="test",
            ),
        ]
    )

    matchup = models.Matchup(
        week=1,
        league_id=league.id,
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=0,
        away_score=0,
    )
    db_session.add(matchup)
    db_session.commit()
    db_session.refresh(matchup)

    recalculate_matchup_scores(db_session, matchup=matchup, season=2026, season_year=2026)
    db_session.commit()
    db_session.refresh(matchup)

    # 250 * 0.04 = 10.0
    assert matchup.home_score == pytest.approx(10.0)
    # 7 * 1.0 = 7.0
    assert matchup.away_score == pytest.approx(7.0)
