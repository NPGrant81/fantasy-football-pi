import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers import draft as draft_router
from backend.services.draft_rankings_service import (
    get_historical_rankings as get_historical_rankings_service,
)


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


def _create_users(db):
    league = models.League(name="L-MODEL-SERVING")
    db.add(league)
    db.commit()
    db.refresh(league)

    commissioner = models.User(
        username="comm-ms",
        hashed_password="pw",
        is_commissioner=True,
        league_id=league.id,
    )
    owner_a = models.User(
        username="owner-ms-a",
        hashed_password="pw",
        is_commissioner=False,
        league_id=league.id,
    )
    owner_b = models.User(
        username="owner-ms-b",
        hashed_password="pw",
        is_commissioner=False,
        league_id=league.id,
    )
    db.add_all([commissioner, owner_a, owner_b])
    db.commit()
    db.refresh(commissioner)
    db.refresh(owner_a)
    db.refresh(owner_b)

    return league, commissioner, owner_a, owner_b


def test_model_predict_blocks_non_commissioner_cross_owner(db_session):
    _, _, owner_a, owner_b = _create_users(db_session)

    payload = draft_router.ModelServingPredictionRequest(
        owner_id=owner_b.id,
        season=2026,
        league_id=owner_a.league_id,
    )

    with pytest.raises(HTTPException) as exc:
        draft_router.predict_model_recommendations(
            payload=payload,
            db=db_session,
            current_user=owner_a,
        )

    assert exc.value.status_code == 403


def test_model_predict_returns_budget_aware_recommendations(db_session, monkeypatch):
    league, commissioner, owner_a, _ = _create_users(db_session)

    def _fake_rankings_service(db, *, season, limit, league_id, owner_id, position, player_ids=None):
        return [
            {
                "player_id": 10,
                "player_name": "Alpha Player",
                "position": "RB",
                "predicted_auction_value": 52.0,
                "final_score": 40.0,
                "consensus_tier": "S",
                "keeper_scarcity_boost": 1.2,
                "scoring_consistency_factor": 1.0,
                "late_start_consistency_factor": 1.0,
                "injury_split_factor": 1.0,
                "team_change_factor": 1.0,
            },
            {
                "player_id": 11,
                "player_name": "Beta Player",
                "position": "WR",
                "predicted_auction_value": 21.0,
                "final_score": 20.0,
                "consensus_tier": "A",
                "keeper_scarcity_boost": 1.0,
                "scoring_consistency_factor": 1.0,
                "late_start_consistency_factor": 1.0,
                "injury_split_factor": 1.0,
                "team_change_factor": 1.0,
            },
        ]

    monkeypatch.setattr(
        draft_router,
        "get_historical_rankings_service",
        _fake_rankings_service,
    )

    payload = draft_router.ModelServingPredictionRequest(
        owner_id=owner_a.id,
        season=2026,
        league_id=league.id,
        model_version="current",
        draft_state=draft_router.ModelServingDraftState(
            drafted_player_ids=[11],
            remaining_budget_by_owner={owner_a.id: 9},
            remaining_slots_by_owner={owner_a.id: 2},
        ),
    )

    response = draft_router.predict_model_recommendations(
        payload=payload,
        db=db_session,
        current_user=commissioner,
    )

    assert response.api_version == "v1"
    assert response.model_version_resolved == "historical-rankings-v1"
    assert response.recommendation_count == 1

    rec = response.recommendations[0]
    assert rec.player_id == 10
    assert rec.recommended_bid == 8.0
    assert rec.within_owner_budget is False
    assert "budget-capped" in rec.flags
    assert "scarcity-boost" in rec.flags


def test_rankings_blocks_non_commissioner_cross_owner(db_session):
    _, _, owner_a, owner_b = _create_users(db_session)

    with pytest.raises(HTTPException) as exc:
        draft_router.get_historical_rankings(
            season=2026,
            league_id=owner_a.league_id,
            owner_id=owner_b.id,
            db=db_session,
            current_user=owner_a,
        )

    assert exc.value.status_code == 403


def test_rankings_service_falls_back_to_player_projections_when_no_draft_values(db_session):
    db_session.add_all(
        [
            models.Player(
                id=9001,
                name="Fallback Alpha",
                position="RB",
                nfl_team="AAA",
                projected_points=280.0,
            ),
            models.Player(
                id=9002,
                name="Fallback Beta",
                position="RB",
                nfl_team="BBB",
                projected_points=240.0,
            ),
            models.Player(
                id=9003,
                name="Fallback Gamma",
                position="WR",
                nfl_team="CCC",
                adp=40.0,
            ),
        ]
    )
    db_session.commit()
    # Required: PlayerSeason records for the fallback query's has_active_season filter
    db_session.add_all([
        models.PlayerSeason(player_id=9001, season=2026, is_active=True),
        models.PlayerSeason(player_id=9002, season=2026, is_active=True),
        models.PlayerSeason(player_id=9003, season=2026, is_active=True),
    ])
    db_session.commit()

    rows = get_historical_rankings_service(
        db_session,
        season=2026,
        limit=10,
        league_id=None,
        owner_id=None,
        position=None,
    )

    assert rows, "Expected fallback rankings to return players"
    assert all(row["season"] == 2026 for row in rows)
    assert rows[0]["player_name"] == "Fallback Alpha"
    assert rows[0]["predicted_auction_value"] >= rows[1]["predicted_auction_value"]
    assert all(row["rank"] >= 1 for row in rows)


def test_rankings_service_dedupes_same_name_across_team_variants(db_session):
    db_session.add_all(
        [
            models.Player(
                id=9101,
                name="Duplicate Alpha",
                position="WR",
                nfl_team="FA",
                projected_points=180.0,
            ),
            models.Player(
                id=9102,
                name="Duplicate Alpha",
                position="WR",
                nfl_team="PIT",
                projected_points=182.0,
            ),
            models.Player(
                id=9103,
                name="Unique Beta",
                position="WR",
                nfl_team="IND",
                projected_points=170.0,
            ),
        ]
    )
    db_session.commit()
    # Required: PlayerSeason records for the fallback query's has_active_season filter
    db_session.add_all([
        models.PlayerSeason(player_id=9101, season=2026, is_active=True),
        models.PlayerSeason(player_id=9102, season=2026, is_active=True),
        models.PlayerSeason(player_id=9103, season=2026, is_active=True),
    ])
    db_session.commit()

    rows = get_historical_rankings_service(
        db_session,
        season=2026,
        limit=10,
        league_id=None,
        owner_id=None,
        position="WR",
    )

    duplicate_rows = [row for row in rows if row["player_name"] == "Duplicate Alpha"]
    assert len(duplicate_rows) == 1
    assert duplicate_rows[0]["player_id"] == 9102


def test_rankings_service_merges_fallback_rows_when_season_is_partial(db_session):
    db_session.add_all(
        [
            models.Player(
                id=9201,
                name="Partial Source WR",
                position="WR",
                nfl_team="AAA",
                projected_points=210.0,
            ),
            models.Player(
                id=9202,
                name="Fallback TE Fill",
                position="TE",
                nfl_team="BBB",
                projected_points=165.0,
            ),
        ]
    )
    db_session.commit()

    db_session.add_all([
        models.PlayerSeason(player_id=9201, season=2026, is_active=True),
        models.PlayerSeason(player_id=9202, season=2026, is_active=True),
    ])
    db_session.commit()

    # Seed only one DraftValue row so the season is partial.
    import models_draft_value as draft_value_models
    db_session.add(
        draft_value_models.DraftValue(
            player_id=9201,
            season=2026,
            avg_auction_value=41.0,
            value_over_replacement=11.0,
            consensus_tier="A",
        )
    )
    db_session.commit()

    rows = get_historical_rankings_service(
        db_session,
        season=2026,
        limit=50,
        league_id=None,
        owner_id=None,
        position=None,
    )

    names = {row["player_name"] for row in rows}
    assert "Partial Source WR" in names
    assert "Fallback TE Fill" in names

    fallback_row = next(row for row in rows if row["player_name"] == "Fallback TE Fill")
    assert fallback_row["predicted_auction_value"] > 0
    assert fallback_row["position"] == "TE"


def test_rankings_service_skips_no_signal_players_in_fallback(db_session):
    db_session.add_all(
        [
            models.Player(
                id=9301,
                name="Signal QB",
                position="QB",
                nfl_team="AAA",
                adp=12.0,
                projected_points=0.0,
            ),
            models.Player(
                id=9302,
                name="No Signal QB",
                position="QB",
                nfl_team="BBB",
                adp=0.0,
                projected_points=0.0,
            ),
        ]
    )
    db_session.commit()

    db_session.add_all([
        models.PlayerSeason(player_id=9301, season=2026, is_active=True),
        models.PlayerSeason(player_id=9302, season=2026, is_active=True),
    ])
    db_session.commit()

    rows = get_historical_rankings_service(
        db_session,
        season=2026,
        limit=50,
        league_id=None,
        owner_id=None,
        position="QB",
    )

    names = {row["player_name"] for row in rows}
    assert "Signal QB" in names
    assert "No Signal QB" not in names


def test_simulation_returns_backend_error_detail(db_session, monkeypatch):
    league, _, owner_a, _ = _create_users(db_session)

    # Seed a player and draft pick so the endpoint doesn't raise 400 "no draft history"
    player = models.Player(id=8001, name="Sim Player", position="QB", nfl_team="AAA")
    db_session.add(player)
    db_session.commit()
    db_session.add(models.DraftPick(
        owner_id=owner_a.id,
        player_id=player.id,
        league_id=league.id,
        amount=30.0,
        year=2026,
        current_status="STARTER",
    ))
    db_session.commit()

    def _raise_simulation_error(**kwargs):
        raise RuntimeError("sim engine unavailable")

    monkeypatch.setattr(draft_router, "run_monte_carlo_draft_simulation", _raise_simulation_error)
    monkeypatch.setattr(Path, "exists", lambda self: True)

    payload = draft_router.DraftSimulationRequest(
        perspective_owner_id=owner_a.id,
        iterations=100,
        teams_count=12,
    )

    with pytest.raises(HTTPException) as exc:
        draft_router.run_draft_simulation(
            payload=payload,
            db=db_session,
            current_user=owner_a,
        )

    assert exc.value.status_code == 500
    assert "sim engine unavailable" in str(exc.value.detail)


# ---------------------------------------------------------------------------
# Regression tests for #159 / #160 fixes
# ---------------------------------------------------------------------------

def test_rankings_service_includes_confidence_score(db_session):
    """confidence_score must be present and non-null in every rankings row (#159 fix)."""
    import models_draft_value as draft_value_models

    db_session.add_all(
        [
            models.Player(id=7701, name="Conf Player A", position="RB", nfl_team="AAA"),
            models.Player(id=7702, name="Conf Player B", position="WR", nfl_team="BBB"),
        ]
    )
    db_session.commit()
    db_session.add_all(
        [
            models.PlayerSeason(player_id=7701, season=2026, is_active=True),
            models.PlayerSeason(player_id=7702, season=2026, is_active=True),
        ]
    )
    db_session.commit()
    db_session.add_all(
        [
            draft_value_models.DraftValue(
                player_id=7701,
                season=2026,
                avg_auction_value=35.0,
                value_over_replacement=8.0,
                consensus_tier="A",
            ),
            draft_value_models.DraftValue(
                player_id=7702,
                season=2026,
                avg_auction_value=20.0,
                value_over_replacement=4.0,
                consensus_tier="B",
            ),
        ]
    )
    db_session.commit()

    rows = get_historical_rankings_service(
        db_session,
        season=2026,
        limit=10,
        league_id=None,
        owner_id=None,
        position=None,
    )

    assert rows, "Expected rankings rows to be returned"
    for row in rows:
        assert "confidence_score" in row, f"confidence_score missing from row {row}"
        assert row["confidence_score"] is not None, "confidence_score must not be None"
        assert 0.0 <= row["confidence_score"] <= 100.0, (
            f"confidence_score {row['confidence_score']} out of [0, 100]"
        )


def test_rankings_service_player_ids_ensures_low_ranked_player_included(db_session):
    """When player_ids is specified, the requested player must appear even if ranked >safe_limit (#159 fix)."""
    import models_draft_value as draft_value_models

    # Create 5 high-value players + 1 low-value target that would normally fall outside limit=5
    high_ids = list(range(7801, 7806))
    target_id = 7806

    players = [
        models.Player(id=pid, name=f"High Player {i}", position="QB", nfl_team="AAA")
        for i, pid in enumerate(high_ids)
    ] + [
        models.Player(id=target_id, name="Low Ranked Target", position="QB", nfl_team="BBB"),
    ]
    db_session.add_all(players)
    db_session.commit()

    seasons = [
        models.PlayerSeason(player_id=pid, season=2026, is_active=True)
        for pid in high_ids + [target_id]
    ]
    db_session.add_all(seasons)
    db_session.commit()

    dv_rows = [
        draft_value_models.DraftValue(
            player_id=pid,
            season=2026,
            avg_auction_value=float(50 - i),  # high players ranked 1-5
            value_over_replacement=float(10 - i),
            consensus_tier="A",
        )
        for i, pid in enumerate(high_ids)
    ] + [
        draft_value_models.DraftValue(
            player_id=target_id,
            season=2026,
            avg_auction_value=1.0,   # lowest value — would be cut by limit=5
            value_over_replacement=0.1,
            consensus_tier="C",
        )
    ]
    db_session.add_all(dv_rows)
    db_session.commit()

    # Without player_ids: limit=5 should exclude the low-ranked target
    rows_no_filter = get_historical_rankings_service(
        db_session,
        season=2026,
        limit=5,
        league_id=None,
        owner_id=None,
        position=None,
    )
    returned_ids_no_filter = {row["player_id"] for row in rows_no_filter}
    assert target_id not in returned_ids_no_filter, (
        "Low-ranked player should be absent when player_ids not specified and limit=5"
    )

    # With player_ids=[target_id]: must be present regardless of rank
    rows_with_filter = get_historical_rankings_service(
        db_session,
        season=2026,
        limit=5,
        league_id=None,
        owner_id=None,
        position=None,
        player_ids=[target_id],
    )
    returned_ids_with_filter = {row["player_id"] for row in rows_with_filter}
    assert target_id in returned_ids_with_filter, (
        "Low-ranked player must be present when explicitly requested via player_ids"
    )
