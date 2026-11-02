from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend import models
from backend.core.security import get_current_user, is_historical_account
from backend.database import get_db
from backend.main import app
from backend.routers.team import get_active_roster_season
from backend.services.historical_auction_service import historical_auction_events
from backend.services.player_service import get_league_free_agents
from backend.services.trade_execution_service import _find_player_pick
from backend.services.waiver_service import process_claim


@pytest.fixture
def observation_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                models.League(id=1, name="one", current_season=2026),
                models.League(id=2, name="two", current_season=2026),
            ]
        )
        db.add(models.LeagueSettings(league_id=1, draft_year=2026, roster_size=16))
        db.add_all(
            [
                models.User(id=1, username="live", league_id=1),
                models.User(
                    id=2,
                    username="hist_2024_0001",
                    league_id=1,
                    is_historical_stub=True,
                ),
            ]
        )
        db.add(models.Player(id=1, name="Brown, AJ", position="WR", nfl_team="PHI"))
        for league_id, season in [(1, 2024), (2, 2023)]:
            db.add(
                models.HistoricalAuctionObservation(
                    league_id=league_id,
                    season=season,
                    owner_id=2,
                    player_id=1,
                    source="mfl",
                    source_event_id="observation",
                    league_mfl_id="11422",
                    player_mfl_id="00123",
                    franchise_id="0001",
                    winning_bid=Decimal("5.010001"),
                    position="WR",
                    nfl_team="TEN",
                    team_labels=["TEN"],
                    plan_sha256="a" * 64,
                    provenance={
                        "event": {
                            "raw_timestamp": "shared-not-chronology",
                            "attributes": {"team_basis": "retain_legacy"},
                        }
                    },
                )
            )
        db.commit()
        yield db
    engine.dispose()


def test_observation_reader_is_season_and_league_scoped_and_exact(observation_db):
    rows = historical_auction_events(observation_db, 1, 2024)
    assert len(rows) == 1
    assert rows[0]["amount"] == "5.010001"
    assert rows[0]["timestamp"] is None
    assert rows[0]["chronology_established"] is False
    assert rows[0]["snapshot_nfl_team"] == "TEN"
    assert rows[0]["owner_label"] == "MFL franchise 0001"
    assert historical_auction_events(observation_db, 1, 2023) == []


def test_history_endpoints_include_observations_without_cross_league_exposure(
    observation_db, client
):
    def database():
        yield observation_db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: observation_db.get(
        models.User, 1
    )
    try:
        response = client.get("/draft/history/by-year?league_id=1&year=2024")
        assert response.status_code == 200
        row = response.json()[0]
        assert row["event_grain"] == "historical_auction_observation"
        assert row["amount"] == "5.010001"
        assert row["timestamp"] is None
        assert "provenance" not in row
        assert (
            client.get("/draft/history/by-year?league_id=2&year=2023").status_code
            == 403
        )
        assert client.get("/draft/seasons?league_id=1").json() == [2026, 2024]
        # Legacy unauthenticated session readers intentionally receive no observations.
        assert client.get("/draft-history?session_id=LEAGUE_1_YEAR_2024").json() == []
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_history_observation_endpoint_requires_authentication(client):
    assert client.get("/draft/history/by-year?league_id=1&year=2024").status_code == 401


def test_observations_do_not_reserve_or_trade_players_or_select_a_live_roster_season(
    observation_db,
):
    db = observation_db
    assert get_active_roster_season(db, 1) == 2026
    assert 1 in [row.id for row in get_league_free_agents(db, 1)]
    assert _find_player_pick(db, league_id=1, owner_id=2, player_id=1) is None
    assert _find_player_pick(db, league_id=1, owner_id=1, player_id=1) is None
    assert is_historical_account(db.get(models.User, 2))
    for model in (
        models.DraftPick,
        models.TransactionHistory,
        models.WaiverBudget,
        models.DraftBudget,
        models.EconomicLedger,
    ):
        assert db.query(model).count() == 0
    result = process_claim(db, db.get(models.User, 1), player_id=1, bid=0)
    assert result is not None
    assert db.query(models.DraftPick).one().year == 2026
    assert db.query(models.HistoricalAuctionObservation).count() == 2
