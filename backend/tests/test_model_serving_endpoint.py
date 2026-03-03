import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers import draft as draft_router


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
