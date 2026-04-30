import os
# force tests to use sqlite in-memory database
os.environ['DATABASE_URL'] = 'sqlite://'

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, status

# The lightweight `client` fixture in conftest supplies a TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core.security import check_is_commissioner
from backend.database import get_db
from backend.main import app


@pytest.fixture
def api_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db, TestingSessionLocal
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_db(api_db):
    db, _ = api_db
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def test_import_schedule_denied_for_non_commissioner(client, api_db):
    # disable commissioner privileges
    async def deny_commissioner():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Commissioner privileges required.",
        )

    app.dependency_overrides[check_is_commissioner] = deny_commissioner

    response = client.post("/admin/nfl/schedule/import", json={"year": 2025})
    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied. Commissioner privileges required."


def test_import_schedule_runs_upsert(client, api_db):
    # allow commission
    async def allow_commissioner():
        # dummy user object
        return models.User(username="c", email="c@test.com", hashed_password="x", is_commissioner=True)

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    # stub the upsert function so we can inspect calls
    # note: the router imports from backend.scripts.import_nfl_schedule
    import backend.scripts.import_nfl_schedule as sched

    calls = []

    def fake_upsert(year, week=None):
        calls.append((year, week))

    sched.upsert_games = fake_upsert

    response = client.post("/admin/nfl/schedule/import", json={"year": 2026, "week": 3})
    assert response.status_code == 200
    assert "Schedule import started" in response.json().get("detail", "")

    # background task should have queued our fake function; TestClient runs it synchronously
    assert calls == [(2026, 3)]


def test_reload_config_endpoint(client, api_db):
    # allow commissioner
    async def allow_commissioner():
        return models.User(username="c", email="c@test.com", hashed_password="x", is_commissioner=True)

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    # make sure a variable is not set, then change .env and reload
    os.environ.pop("TEST_RELOAD_KEY", None)
    # simulate writing to .env by writing to a temp file and pointing load_dotenv there
    with open(".env", "w") as f:
        f.write("TEST_RELOAD_KEY=hello\n")

    response = client.post("/admin/config/reload")
    assert response.status_code == 200
    assert response.json()["reloaded"] is True
    assert os.environ.get("TEST_RELOAD_KEY") == "hello"


def test_live_score_ingest_dry_run_endpoint(client, api_db):
    async def allow_commissioner():
        return models.User(username="c", email="c@test.com", hashed_password="x", is_commissioner=True)

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    import backend.services.live_scoring_ingest_service as ingest

    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return {
            "status": "success",
            "mode": "dry_run",
            "year": kwargs["year"],
            "week": kwargs["week"],
            "degraded": False,
            "fetch_diagnostics": {"attempts": [{"status": "success"}]},
        }

    ingest.run_live_scoreboard_ingest_with_controls = fake_run

    response = client.post(
        "/admin/live-scoring/ingest",
        json={
            "year": 2026,
            "week": 2,
            "dry_run": True,
            "timeout_seconds": 15,
            "override_url": "https://mirror.example/scoreboard",
            "enable_failover": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["mode"] == "dry_run"
    assert body["degraded"] is False

    assert len(calls) == 1
    assert calls[0]["year"] == 2026
    assert calls[0]["week"] == 2
    assert calls[0]["dry_run"] is True
    assert calls[0]["timeout_seconds"] == 15
    assert calls[0]["override_url"] == "https://mirror.example/scoreboard"
    assert calls[0]["enable_failover"] is False


def test_live_score_ingest_endpoint_returns_502_with_diagnostics(client, api_db):
    async def allow_commissioner():
        return models.User(username="c", email="c@test.com", hashed_password="x", is_commissioner=True)

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    import backend.services.live_scoring_ingest_service as ingest

    def fake_run(**kwargs):
        raise ingest.IngestFetchError(
            "all urls failed",
            diagnostics={
                "attempts": [
                    {
                        "attempt": 1,
                        "url": "https://bad.example",
                        "status": "failed",
                        "error": "ConnectTimeout",
                    }
                ],
                "degraded": True,
            },
        )

    ingest.run_live_scoreboard_ingest_with_controls = fake_run

    response = client.post("/admin/live-scoring/ingest", json={"year": 2026, "dry_run": True})
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_signature"] == "IngestFetchError"
    assert detail["fetch_diagnostics"]["degraded"] is True


def test_live_score_ingest_health_endpoint(client, api_db):
    async def allow_commissioner():
        return models.User(username="c", email="c@test.com", hashed_password="x", is_commissioner=True)

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    import backend.services.live_scoring_ingest_service as ingest

    def fake_summary(limit: int = 100):
        return {
            "runs_considered": 2,
            "success_runs": 1,
            "failed_runs": 1,
            "degraded_runs": 1,
            "failure_rate": 0.5,
            "last_run": {"status": "failed"},
            "top_error_signatures": [{"error_signature": "IngestFetchError", "count": 1}],
            "runs": [{"status": "success"}, {"status": "failed"}],
            "limit_seen": limit,
        }

    ingest.summarize_ingest_health = fake_summary

    response = client.get("/admin/live-scoring/health?limit=25")
    assert response.status_code == 200
    body = response.json()
    assert body["runs_considered"] == 2
    assert body["failure_rate"] == 0.5
    assert body["limit_seen"] == 25


def test_live_score_watchdog_run_endpoint(client, api_db):
    async def allow_commissioner():
        return models.User(username="c", email="c@test.com", hashed_password="x", is_commissioner=True)

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    import backend.services.live_scoring_watchdog_service as watchdog

    def fake_run_watchdog(limit: int | None = None, thresholds=None):
        return {
            "checked_at": "2026-03-14T19:10:00Z",
            "alert_count": 1,
            "alerts": [{"alert_type": "failure_rate"}],
            "health_summary": {"runs_considered": limit},
        }

    watchdog.run_watchdog_check = fake_run_watchdog

    response = client.post("/admin/live-scoring/watchdog", json={"limit": 12})
    assert response.status_code == 200
    body = response.json()
    assert body["alert_count"] == 1
    assert body["health_summary"]["runs_considered"] == 12


def test_live_score_watchdog_alerts_endpoint(client, api_db):
    async def allow_commissioner():
        return models.User(username="c", email="c@test.com", hashed_password="x", is_commissioner=True)

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    import backend.services.live_scoring_watchdog_service as watchdog

    def fake_load_alerts(limit: int = 100):
        return [{"checked_at": "2026-03-14T19:10:00Z", "alert_count": 2, "limit_seen": limit}]

    watchdog.load_recent_watchdog_alerts = fake_load_alerts

    response = client.get("/admin/live-scoring/watchdog/alerts?limit=7")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 7
    assert len(body["alerts"]) == 1
    assert body["alerts"][0]["limit_seen"] == 7


def test_refresh_draft_values_enqueues_background_task(client, api_db, monkeypatch):
    async def allow_commissioner():
        return models.User(username="c", email="c@test.com", hashed_password="x", is_commissioner=True)

    app.dependency_overrides[check_is_commissioner] = allow_commissioner

    import backend.routers.admin_drafts as admin_drafts

    calls = []

    def fake_run(payload):
        calls.append(payload)

    monkeypatch.setattr(admin_drafts, "_run_draft_values_refresh", fake_run)

    response = client.post(
        "/admin/drafts/refresh-values",
        json={
            "season": 2026,
            "sources": ["fantasynerds"],
            "fantasynerds_api_key": "k",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["season"] == 2026
    assert body["sources"] == ["fantasynerds"]
    assert len(calls) == 1


def test_refresh_draft_values_fantasynerds_precheck_blocks_load(monkeypatch):
    import pandas as pd
    import backend.database as database
    import backend.routers.admin_drafts as admin_drafts
    import etl.extract.extract_fantasynerds as fantasynerds
    import etl.load.load_to_postgres as loader
    import etl.services.consensus_service as consensus

    payload = admin_drafts.RefreshDraftValuesPayload(
        season=2026,
        sources=["fantasynerds"],
        fantasynerds_api_key="k",
        enforce_fantasynerds_precheck=True,
        fantasynerds_min_players=10,
    )

    loaded = []

    class _DummySession:
        def close(self):
            return None

    def fake_fetch(*args, **kwargs):
        return pd.DataFrame([{"name": "A", "position": "QB", "team": "BUF"}])

    def fake_transform(*args, **kwargs):
        return pd.DataFrame(
            [
                {
                    "normalized_name": "a",
                    "position": "QB",
                    "team": "BUF",
                    "adp": 1.0,
                    "auction_value": None,
                    "auction_value_min": None,
                    "auction_value_max": None,
                }
            ]
        )

    def fake_load(*args, **kwargs):
        loaded.append(kwargs)

    monkeypatch.setattr(fantasynerds, "fetch_fantasynerds_auction_values", fake_fetch)
    monkeypatch.setattr(fantasynerds, "transform_fantasynerds_auction_values", fake_transform)
    monkeypatch.setattr(loader, "load_normalized_source_to_db", fake_load)
    monkeypatch.setattr(database, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(consensus, "build_and_store_consensus_draft_values", lambda db, season: {"updated": 0})

    admin_drafts._run_draft_values_refresh(payload)
    assert loaded == []


def test_refresh_draft_values_fantasynerds_precheck_passes_and_loads(monkeypatch):
    import pandas as pd
    import backend.database as database
    import backend.routers.admin_drafts as admin_drafts
    import etl.extract.extract_fantasynerds as fantasynerds
    import etl.load.load_to_postgres as loader
    import etl.services.consensus_service as consensus

    payload = admin_drafts.RefreshDraftValuesPayload(
        season=2026,
        sources=["fantasynerds"],
        fantasynerds_api_key="k",
        enforce_fantasynerds_precheck=True,
        fantasynerds_min_players=1,
        fantasynerds_min_auction_coverage=0.0,
        fantasynerds_min_minmax_coverage=0.0,
    )

    loaded = []

    class _DummySession:
        def close(self):
            return None

    def fake_fetch(*args, **kwargs):
        return pd.DataFrame([{"name": "A", "position": "QB", "team": "BUF"}])

    def fake_transform(*args, **kwargs):
        return pd.DataFrame(
            [
                {
                    "normalized_name": "a",
                    "position": "QB",
                    "team": "BUF",
                    "adp": 1.0,
                    "auction_value": 12.0,
                    "auction_value_min": 10.0,
                    "auction_value_max": 14.0,
                }
            ]
        )

    def fake_load(norm_df, season, source):
        loaded.append((len(norm_df), season, source))

    monkeypatch.setattr(fantasynerds, "fetch_fantasynerds_auction_values", fake_fetch)
    monkeypatch.setattr(fantasynerds, "transform_fantasynerds_auction_values", fake_transform)
    monkeypatch.setattr(loader, "load_normalized_source_to_db", fake_load)
    monkeypatch.setattr(database, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(consensus, "build_and_store_consensus_draft_values", lambda db, season: {"updated": 0})

    admin_drafts._run_draft_values_refresh(payload)
    assert loaded == [(1, 2026, "FantasyNerds")]


def test_refresh_draft_values_yahoo_precheck_blocks_load(monkeypatch):
    import backend.database as database
    import backend.routers.admin_drafts as admin_drafts
    import etl.extract.extract_yahoo as yahoo
    import etl.extract.extract_yahoo_precheck as yahoo_precheck
    import etl.load.load_to_postgres as loader
    import etl.services.consensus_service as consensus

    payload = admin_drafts.RefreshDraftValuesPayload(
        season=2026,
        sources=[],
        include_yahoo=True,
        enforce_yahoo_precheck=True,
        yahoo_min_players=10,
        yahoo_min_adp_coverage=1.0,
    )

    loaded = []

    class _DummySession:
        def close(self):
            return None

    monkeypatch.setattr(yahoo, "fetch_yahoo_top_players", lambda max_players=100: [{"Name": "A", "Position": "QB", "Team": "BUF", "ADP": 0}])
    monkeypatch.setattr(
        yahoo,
        "transform_yahoo_players",
        lambda players, league_size=12: [{"normalized_name": "a", "position": "QB", "team": "BUF", "adp": 0}],
    )
    monkeypatch.setattr(loader, "load_normalized_source_to_db", lambda *args, **kwargs: loaded.append(1))
    monkeypatch.setattr(database, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(consensus, "build_and_store_consensus_draft_values", lambda db, season: {"updated": 0})

    # Keep evaluator real to validate threshold behavior for adp=0 rows.
    assert callable(yahoo_precheck.evaluate_yahoo_quality)

    admin_drafts._run_draft_values_refresh(payload)
    assert loaded == []


def test_refresh_draft_values_yahoo_precheck_passes_and_loads(monkeypatch):
    import backend.database as database
    import backend.routers.admin_drafts as admin_drafts
    import etl.extract.extract_yahoo as yahoo
    import etl.load.load_to_postgres as loader
    import etl.services.consensus_service as consensus

    payload = admin_drafts.RefreshDraftValuesPayload(
        season=2026,
        sources=[],
        include_yahoo=True,
        enforce_yahoo_precheck=True,
        yahoo_min_players=1,
        yahoo_min_adp_coverage=0.0,
    )

    loaded = []

    class _DummySession:
        def close(self):
            return None

    monkeypatch.setattr(yahoo, "fetch_yahoo_top_players", lambda max_players=100: [{"Name": "A", "Position": "QB", "Team": "BUF", "ADP": 1}])
    monkeypatch.setattr(
        yahoo,
        "transform_yahoo_players",
        lambda players, league_size=12: [{"normalized_name": "a", "position": "QB", "team": "BUF", "adp": 1.0}],
    )

    def fake_load(norm_df, season, source):
        loaded.append((len(norm_df), season, source))

    monkeypatch.setattr(loader, "load_normalized_source_to_db", fake_load)
    monkeypatch.setattr(database, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(consensus, "build_and_store_consensus_draft_values", lambda db, season: {"updated": 0})

    admin_drafts._run_draft_values_refresh(payload)
    assert loaded == [(1, 2026, "Yahoo")]
