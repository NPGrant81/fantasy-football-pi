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

    def _fake_rankings_service(db, *, season, limit, league_id, owner_id, position):
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
