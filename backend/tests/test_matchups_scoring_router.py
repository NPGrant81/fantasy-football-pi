import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.matchups import (
    calculate_win_probabilities,
    fetch_matchup_detail_data as get_matchup_detail,
    get_team_starters,
    get_weekly_matchups,
)
from backend.routers.players import get_player_season_details


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
                year=2025,
                current_status="STARTER",
            ),
            models.DraftPick(
                owner_id=away.id,
                player_id=away_wr.id,
                league_id=league.id,
                year=2025,
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
        season=2026,
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
        "home_player_id": home_qb.id,
        "away_player_id": away_wr.id,
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


def test_player_and_matchup_detail_share_point_provenance_semantics(db_session):
    seeded = _seed_matchup_data(db_session)

    player_details = get_player_season_details(
        seeded["home_player_id"],
        season=2026,
        db=db_session,
    )
    matchup_details = get_matchup_detail(seeded["matchup_id"], db_session)

    player_points = player_details["semantic_context"]["points"]
    matchup_player = matchup_details.home_roster[0]
    actual_points = matchup_player.semantic_context.actual
    projected_points = matchup_player.semantic_context.projected

    assert player_details["total_fantasy_points"] == pytest.approx(18.0)
    assert player_points["source_status"] == actual_points.source_status == "known"
    assert player_points["sources"] == actual_points.sources == ["test"]
    assert player_points["value_basis"] == actual_points.value_basis == "source_reported"
    assert player_points["freshness"] == actual_points.freshness == "unknown"
    assert projected_points.value_basis == "league_calculated"
    assert projected_points.scoring_definition == "unversioned"
    assert matchup_player.semantic_context.membership.historical_status == "current_only"
    assert matchup_player.semantic_context.membership.season_scoped is False
    assert matchup_player.semantic_context.membership.week_scoped is False


def test_player_season_aggregate_preserves_all_sources_and_marks_mixed_context(db_session):
    seeded = _seed_matchup_data(db_session)
    db_session.add(
        models.PlayerWeeklyStat(
            player_id=seeded["home_player_id"],
            season=2026,
            week=3,
            stats={"passing_yards": 250},
            fantasy_points=21.0,
            source="provider_b",
        )
    )
    db_session.commit()

    details = get_player_season_details(
        seeded["home_player_id"],
        season=2026,
        db=db_session,
    )

    semantic_points = details["semantic_context"]["points"]
    assert details["total_fantasy_points"] == pytest.approx(39.0)
    assert details["games_played"] == 2
    assert semantic_points["source_status"] == "mixed"
    assert semantic_points["sources"] == ["provider_b", "test"]
    assert semantic_points["selection_policy"] == "all_available_source_rows"
    assert {row["source"] for row in details["weekly"]} == {"provider_b", "test"}


def test_player_season_details_preserves_unknown_source_and_missing_points(db_session):
    seeded = _seed_matchup_data(db_session)
    stat = (
        db_session.query(models.PlayerWeeklyStat)
        .filter_by(player_id=seeded["home_player_id"], season=2026, week=3)
        .one()
    )
    stat.source = None
    stat.fantasy_points = None
    db_session.commit()

    details = get_player_season_details(
        seeded["home_player_id"],
        season=2026,
        db=db_session,
    )
    semantic_points = details["semantic_context"]["points"]

    assert details["total_fantasy_points"] == 0.0
    assert details["weekly"][0]["fantasy_points"] == 0.0
    assert semantic_points["source_status"] == "unknown"
    assert semantic_points["value_basis"] == "unknown"
    assert semantic_points["value_status"] == "unknown"
    assert semantic_points["unknown_source_count"] == 1
    assert semantic_points["freshness"] == "unknown"


def test_matchup_actual_points_remain_unknown_without_source_provenance(db_session):
    seeded = _seed_matchup_data(db_session)
    stat = (
        db_session.query(models.PlayerWeeklyStat)
        .filter_by(player_id=seeded["home_player_id"], season=2026, week=3)
        .one()
    )
    stat.source = None
    db_session.commit()

    matchup = get_matchup_detail(seeded["matchup_id"], db_session)
    home_player = matchup.home_roster[0]

    assert home_player.actual == pytest.approx(18.0)
    assert home_player.semantic_context.actual.value_basis == "unknown"
    assert home_player.semantic_context.actual.source_status == "unknown"
    assert home_player.semantic_context.actual.value_status == "known"
    assert home_player.semantic_context.projected.value_basis == "league_calculated"


def test_missing_source_provenance_does_not_mark_present_points_unknown(db_session):
    seeded = _seed_matchup_data(db_session)
    stat = (
        db_session.query(models.PlayerWeeklyStat)
        .filter_by(player_id=seeded["home_player_id"], season=2026, week=3)
        .one()
    )
    stat.source = None
    db_session.commit()

    details = get_player_season_details(
        seeded["home_player_id"],
        season=2026,
        db=db_session,
    )
    semantic_points = details["semantic_context"]["points"]

    assert semantic_points["value_status"] == "known"
    assert semantic_points["value_basis"] == "unknown"
    assert semantic_points["unknown_value_count"] == 0
    assert semantic_points["unknown_source_count"] == 1


def test_matchup_context_exposes_aggregate_basis_and_unknown_stored_scores(db_session):
    seeded = _seed_matchup_data(db_session)
    home_user = db_session.query(models.User).filter_by(id=seeded["home_id"]).one()

    [weekly_matchup] = get_weekly_matchups(3, db_session, home_user)

    assert weekly_matchup.home_roster == []
    assert weekly_matchup.semantic_context.scope.season == 2026
    assert weekly_matchup.semantic_context.calculation_scope.season == 2026
    assert weekly_matchup.semantic_context.home_projected.sources == ["test"]
    assert weekly_matchup.semantic_context.home_projected.value_basis == "league_calculated"
    assert weekly_matchup.semantic_context.stored_scores.value_basis == "unknown"
    assert weekly_matchup.semantic_context.stored_scores.value_status == "unknown"
    assert weekly_matchup.semantic_context.stored_scores.freshness == "unknown"
    assert weekly_matchup.semantic_context.membership.historical_status == "current_only"


def test_matchup_detail_marks_legacy_picks_as_current_only_membership(db_session):
    seeded = _seed_matchup_data(db_session)
    legacy_player = models.Player(name="Legacy TE", position="TE", nfl_team="DDD")
    db_session.add(legacy_player)
    db_session.commit()
    db_session.refresh(legacy_player)
    db_session.add(
        models.DraftPick(
            owner_id=seeded["home_id"],
            player_id=legacy_player.id,
            league_id=None,
            year=2024,
            current_status="STARTER",
        )
    )
    db_session.commit()

    matchup = get_matchup_detail(seeded["matchup_id"], db_session)
    legacy_row = next(row for row in matchup.home_roster if row.player_id == legacy_player.id)

    assert legacy_row.semantic_context.membership.league_scoped is False
    assert legacy_row.semantic_context.membership.allows_unscoped_legacy_picks is True
    assert legacy_row.semantic_context.membership.season_scoped is False
    assert legacy_row.semantic_context.membership.historical_status == "current_only"


def test_get_team_starters_isolates_by_league(db_session):
    """Picks from a different league must not appear in another league's starters."""
    seeded = _seed_matchup_data(db_session)

    # Create a second league and add a starter pick for home user in that league.
    other_league = models.League(name="Other League")
    db_session.add(other_league)
    db_session.commit()
    db_session.refresh(other_league)

    other_player = models.Player(name="Other RB", position="RB", nfl_team="CCC")
    db_session.add(other_player)
    db_session.commit()
    db_session.refresh(other_player)

    db_session.add(
        models.DraftPick(
            owner_id=seeded["home_id"],
            player_id=other_player.id,
            league_id=other_league.id,
            current_status="STARTER",
        )
    )
    db_session.commit()

    home_starters = get_team_starters(
        db_session,
        seeded["home_id"],
        league_id=seeded["league_id"],
        season=2026,
        week=3,
    )

    # Only the starter from the correct league should appear; the other-league
    # pick must not contaminate the result.
    assert len(home_starters) == 1
    assert home_starters[0].name != "Other RB"


def test_get_team_starters_includes_null_league_id_picks(db_session):
    """Legacy picks with NULL league_id should be included when league_id is given."""
    seeded = _seed_matchup_data(db_session)

    legacy_player = models.Player(name="Legacy TE", position="TE", nfl_team="DDD")
    db_session.add(legacy_player)
    db_session.commit()
    db_session.refresh(legacy_player)

    db_session.add(
        models.DraftPick(
            owner_id=seeded["home_id"],
            player_id=legacy_player.id,
            league_id=None,
            current_status="STARTER",
        )
    )
    db_session.commit()

    home_starters = get_team_starters(
        db_session,
        seeded["home_id"],
        league_id=seeded["league_id"],
        season=2026,
        week=3,
    )

    player_names = [s.name for s in home_starters]
    assert "Legacy TE" in player_names


def test_get_matchup_detail_aggregates_projected_from_scored_starters(db_session):
    seeded = _seed_matchup_data(db_session)

    payload = get_matchup_detail(seeded["matchup_id"], db_session)

    assert payload.home_projected == pytest.approx(10.0)
    assert payload.away_projected == pytest.approx(6.0)
    assert payload.home_roster[0].projected == pytest.approx(10.0)
    assert payload.away_roster[0].projected == pytest.approx(6.0)
    assert payload.home_win_probability == pytest.approx(62.5)
    assert payload.away_win_probability == pytest.approx(37.5)


def test_calculate_win_probabilities_handles_zero_projection_totals():
    home_probability, away_probability = calculate_win_probabilities(0.0, 0.0)

    assert home_probability == pytest.approx(50.0)
    assert away_probability == pytest.approx(50.0)


def test_get_matchup_detail_handles_empty_away_roster(db_session):
    """Game-center payload should remain valid when one side has no active starters."""
    seeded = _seed_matchup_data(db_session)

    db_session.query(models.DraftPick).filter(
        models.DraftPick.owner_id == seeded["away_id"],
        models.DraftPick.current_status == "STARTER",
    ).delete()
    db_session.commit()

    payload = get_matchup_detail(seeded["matchup_id"], db_session)

    assert payload.home_projected == pytest.approx(10.0)
    assert payload.away_projected == pytest.approx(0.0)
    assert len(payload.home_roster) == 1
    assert payload.away_roster == []
    assert payload.home_win_probability == pytest.approx(100.0)
    assert payload.away_win_probability == pytest.approx(0.0)
