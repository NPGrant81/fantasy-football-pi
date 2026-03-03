import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from backend.routers.advisor import (
    DraftDayEventRequest,
    DraftDayQueryRequest,
    DraftDayState,
    draft_day_event,
    draft_day_query,
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


def _mock_rankings(*args, **kwargs):
    return [
        {
            "player_id": 101,
            "player_name": "Alpha RB",
            "position": "RB",
            "predicted_auction_value": 24.0,
            "consensus_tier": "A",
            "final_score": 89.5,
            "scoring_consistency_factor": 1.0,
            "late_start_consistency_factor": 1.0,
            "injury_split_factor": 1.0,
            "team_change_factor": 1.0,
        },
        {
            "player_id": 102,
            "player_name": "Beta RB",
            "position": "RB",
            "predicted_auction_value": 18.0,
            "consensus_tier": "B",
            "final_score": 82.0,
            "scoring_consistency_factor": 0.9,
            "late_start_consistency_factor": 0.95,
            "injury_split_factor": 0.95,
            "team_change_factor": 1.0,
        },
        {
            "player_id": 201,
            "player_name": "Gamma WR",
            "position": "WR",
            "predicted_auction_value": 20.0,
            "consensus_tier": "A",
            "final_score": 88.0,
            "scoring_consistency_factor": 1.0,
            "late_start_consistency_factor": 0.98,
            "injury_split_factor": 0.98,
            "team_change_factor": 1.0,
        },
    ]


def test_draft_day_nomination_response(monkeypatch, db_session):
    monkeypatch.setattr("backend.routers.advisor.get_historical_rankings", _mock_rankings)

    request = DraftDayEventRequest(
        owner_id=1,
        season=2025,
        league_id=10,
        event_type="nomination",
        player_id=101,
        current_bid=12,
        draft_state=DraftDayState(
            drafted_player_ids=[300, 301],
            remaining_budget_by_owner={1: 16},
            remaining_slots_by_owner={1: 5},
            position_counts_by_owner={1: {"RB": 3, "WR": 1}},
            recent_nominations=["RB", "RB", "RB", "RB"],
        ),
    )

    response = draft_day_event(request, db=db_session)

    assert response.message_type == "recommendation"
    assert response.headline.startswith("Nomination guidance")
    assert response.recommended_bid == pytest.approx(12.0)
    assert "WR-light" in " ".join(response.alerts)
    assert "run appears to be starting" in " ".join(response.alerts)
    assert response.quick_actions == ["Compare", "Simulate", "Explain"]


def test_draft_day_bid_update_alert_when_price_too_high(monkeypatch, db_session):
    monkeypatch.setattr("backend.routers.advisor.get_historical_rankings", _mock_rankings)

    request = DraftDayEventRequest(
        owner_id=2,
        season=2025,
        league_id=10,
        event_type="bid_update",
        player_id=101,
        current_bid=22,
        draft_state=DraftDayState(
            remaining_budget_by_owner={2: 10},
            remaining_slots_by_owner={2: 3},
        ),
    )

    response = draft_day_event(request, db=db_session)

    assert response.message_type == "alert"
    assert response.recommended_bid == pytest.approx(8.0)
    assert "above your plan" in response.body


def test_draft_day_query_compare_response(monkeypatch, db_session):
    monkeypatch.setattr("backend.routers.advisor.get_historical_rankings", _mock_rankings)

    request = DraftDayQueryRequest(
        owner_id=1,
        season=2025,
        league_id=10,
        player_id=101,
        compared_player_id=201,
        question="Compare these two players",
    )

    response = draft_day_query(request, db=db_session)

    assert response.message_type == "comparison"
    assert "Comparison:" in response.headline
    assert "Preferred target" in response.body
