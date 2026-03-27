import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers import draft as draft_router
from etl.transform.monte_carlo_simulation import MonteCarloSimulationResult


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


def _create_league_and_users(db):
    league = models.League(name="Simulation League")
    db.add(league)
    db.commit()
    db.refresh(league)

    commissioner = models.User(
        username="commish-sim",
        hashed_password="pw",
        is_commissioner=True,
        league_id=league.id,
    )
    owner_a = models.User(
        username="owner-a",
        hashed_password="pw",
        is_commissioner=False,
        league_id=league.id,
    )
    owner_b = models.User(
        username="owner-b",
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


def test_simulation_endpoint_rejects_non_commissioner_cross_owner_request(db_session):
    _, _, owner_a, owner_b = _create_league_and_users(db_session)

    payload = draft_router.DraftSimulationRequest(
        perspective_owner_id=owner_b.id,
        iterations=100,
    )

    with pytest.raises(HTTPException) as exc:
        draft_router.run_draft_simulation(
            payload=payload,
            db=db_session,
            current_user=owner_a,
        )

    assert exc.value.status_code == 403


def test_simulation_endpoint_returns_focal_strategy_payload(db_session, monkeypatch):
    league, commissioner, owner_a, _ = _create_league_and_users(db_session)

    # Seed a player and draft pick so the endpoint doesn't raise 400 "no draft history"
    player = models.Player(id=101, name="Player One", position="RB", nfl_team="AAA")
    db_session.add(player)
    db_session.commit()
    db_session.add(models.DraftPick(
        owner_id=owner_a.id,
        player_id=player.id,
        league_id=league.id,
        amount=45.0,
        year=2026,
        current_status="STARTER",
    ))
    db_session.commit()

    def _fake_run_monte_carlo_simulation(**kwargs):
        picks = pd.DataFrame(
            [
                {
                    "iteration": 1,
                    "owner_id": owner_a.id,
                    "player_id": 101,
                    "player_name": "Player One",
                    "predicted_auction_value": 45.0,
                },
                {
                    "iteration": 2,
                    "owner_id": owner_a.id,
                    "player_id": 102,
                    "player_name": "Player Two",
                    "predicted_auction_value": 40.0,
                },
            ]
        )
        team_metrics = pd.DataFrame(
            [
                {
                    "iteration": 1,
                    "owner_id": owner_a.id,
                    "projected_points": 150.0,
                    "total_spend": 180.0,
                },
                {
                    "iteration": 1,
                    "owner_id": commissioner.id,
                    "projected_points": 140.0,
                    "total_spend": 170.0,
                },
            ]
        )
        owner_summary = pd.DataFrame(
            [
                {
                    "owner_id": owner_a.id,
                    "expected_total_points": 150.0,
                    "expected_total_spend": 180.0,
                }
            ]
        )
        return MonteCarloSimulationResult(
            draft_picks=picks,
            team_metrics=team_metrics,
            owner_summary=owner_summary,
            assumptions={"ok": True},
        )

    monkeypatch.setattr(draft_router, "run_monte_carlo_draft_simulation", _fake_run_monte_carlo_simulation)

    payload = draft_router.DraftSimulationRequest(
        perspective_owner_id=owner_a.id,
        iterations=120,
        strategy=draft_router.FocalOwnerStrategyKnobs(
            aggressiveness_multiplier=1.3,
            position_weights={"RB": 1.25, "WR": 0.9},
            risk_tolerance=0.7,
            player_reliability_weight=1.4,
        ),
    )

    response = draft_router.run_draft_simulation(
        payload=payload,
        db=db_session,
        current_user=commissioner,
    )

    assert response["perspective_owner_id"] == owner_a.id
    assert response["iterations"] == 120
    assert response["focal_owner_summary"]["owner_id"] == owner_a.id
    assert response["used_strategy"]["aggressiveness_multiplier"] == 1.3
    assert response["used_strategy"]["position_weights"]["RB"] == 1.25
    assert len(response["key_target_probabilities"]) > 0
