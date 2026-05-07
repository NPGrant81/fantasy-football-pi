"""
Tests for live_scoring_event_bus and the live_scoring_sse router.
"""

import asyncio
import json
import types

import pytest
from fastapi.testclient import TestClient

from backend.services import live_scoring_event_bus as bus


# ---------------------------------------------------------------------------
# Reset bus state between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_bus():
    """Clear subscriptions and loop reference before each test."""
    with bus._lock:
        bus._clients.clear()
    bus._loop = None
    yield
    with bus._lock:
        bus._clients.clear()
    bus._loop = None


# ---------------------------------------------------------------------------
# Event bus unit tests
# ---------------------------------------------------------------------------


def test_subscribe_creates_queue_and_registers_client():
    q = bus.subscribe()
    assert bus.get_client_count() == 1
    assert isinstance(q, asyncio.Queue)


def test_unsubscribe_removes_client():
    q = bus.subscribe()
    bus.unsubscribe(q)
    assert bus.get_client_count() == 0


def test_unsubscribe_unknown_queue_is_noop():
    q: asyncio.Queue = asyncio.Queue()
    bus.unsubscribe(q)  # should not raise
    assert bus.get_client_count() == 0


def test_publish_from_thread_no_loop_is_noop():
    q = bus.subscribe()
    # No loop registered — publish should be silent
    bus.publish_from_thread({"event": "score_update"})
    assert q.empty()


def test_publish_from_thread_no_clients_is_noop():
    # No subscriptions — should not raise
    loop = asyncio.new_event_loop()
    bus.set_event_loop(loop)
    bus.publish_from_thread({"event": "score_update"})
    loop.close()


def test_publish_from_thread_delivers_event():
    loop = asyncio.new_event_loop()
    bus.set_event_loop(loop)
    q = bus.subscribe()

    event = {"event": "score_update", "year": 2026, "week": 14}
    bus.publish_from_thread(event)

    # Allow the scheduled coroutine to execute
    loop.run_until_complete(asyncio.sleep(0.05))

    assert not q.empty()
    received = q.get_nowait()
    assert received["event"] == "score_update"
    assert received["week"] == 14

    loop.close()


def test_publish_from_thread_drops_oldest_when_queue_full():
    loop = asyncio.new_event_loop()
    bus.set_event_loop(loop)
    q = bus.subscribe()

    # Fill the queue to capacity
    for i in range(bus._QUEUE_MAXSIZE):
        loop.run_until_complete(q.put({"seq": i}))

    assert q.full()

    # Publishing one more should evict the oldest and add the new one
    new_event = {"event": "score_update", "year": 2026, "week": 1}
    bus.publish_from_thread(new_event)
    loop.run_until_complete(asyncio.sleep(0.05))

    # Queue should still be at max size (evict + add)
    assert q.qsize() == bus._QUEUE_MAXSIZE

    # Drain and check last item
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    assert items[-1]["event"] == "score_update"

    loop.close()


def test_build_score_update_event_structure():
    event = bus.build_score_update_event(
        year=2026,
        week=14,
        active_games=3,
        is_active_window=True,
        state_transitions=[{"event_id": "401", "from": "live", "to": "final"}],
        scoreboard_fingerprint="abc123",
        matchup_projection_snapshots=[{"matchup_id": 1, "home_projected": 95.5}],
    )
    assert event["event"] == "score_update"
    assert event["year"] == 2026
    assert event["week"] == 14
    assert event["active_games"] == 3
    assert event["is_active_window"] is True
    assert len(event["state_transitions"]) == 1
    assert event["scoreboard_fingerprint"] == "abc123"
    assert event["matchup_projection_snapshots"][0]["home_projected"] == 95.5
    assert isinstance(event["ts"], int)


def test_build_score_update_event_none_snapshots_defaults_to_empty_list():
    event = bus.build_score_update_event(
        year=2026,
        week=1,
        active_games=0,
        is_active_window=False,
        state_transitions=[],
        scoreboard_fingerprint=None,
        matchup_projection_snapshots=None,
    )
    assert event["matchup_projection_snapshots"] == []


# ---------------------------------------------------------------------------
# SSE router integration tests
# ---------------------------------------------------------------------------


def _make_test_client():
    """Build a minimal FastAPI app with just the SSE router."""
    from fastapi import FastAPI
    from backend.routers.live_scoring_sse import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=True)


def test_sse_stream_returns_event_stream_content_type():
    client = _make_test_client()
    # Open the stream with a short timeout so the test doesn't hang
    with client.stream("GET", "/live-scoring/stream") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]


def test_sse_stream_registers_and_unregisters_client():
    before = bus.get_client_count()
    client = _make_test_client()
    with client.stream("GET", "/live-scoring/stream"):
        during = bus.get_client_count()
        assert during == before + 1
    # After closing the stream the client should be unsubscribed
    after = bus.get_client_count()
    assert after == before


def test_sse_stream_delivers_published_event():
    loop = asyncio.new_event_loop()
    bus.set_event_loop(loop)

    event = bus.build_score_update_event(
        year=2026,
        week=5,
        active_games=2,
        is_active_window=True,
        state_transitions=[],
        scoreboard_fingerprint="fp99",
        matchup_projection_snapshots=[],
    )

    client = _make_test_client()

    received_lines = []

    # We need to publish after the client has subscribed, so we use a
    # background thread triggered by the streaming iterator.
    import threading

    def _publish_after_subscribe():
        # Wait briefly for the SSE connection to open and subscribe
        import time
        time.sleep(0.1)
        bus.publish_from_thread(event)
        loop.run_until_complete(asyncio.sleep(0.05))

    publisher = threading.Thread(target=_publish_after_subscribe, daemon=True)
    publisher.start()

    with client.stream("GET", "/live-scoring/stream") as resp:
        for raw_line in resp.iter_lines():
            if raw_line.startswith("data:"):
                received_lines.append(raw_line)
                break  # stop after first data line

    publisher.join(timeout=2)
    loop.close()

    assert len(received_lines) == 1
    payload = json.loads(received_lines[0].removeprefix("data:").strip())
    assert payload["event"] == "score_update"
    assert payload["week"] == 5
    assert payload["scoreboard_fingerprint"] == "fp99"


# ---------------------------------------------------------------------------
# Polling service integration: publish on downstream_updates_triggered
# ---------------------------------------------------------------------------


def test_poll_cycle_publishes_event_on_change(monkeypatch):
    """When a poll cycle detects a change, publish_from_thread is called."""
    from backend.services import live_scoring_polling_service as polling

    published = []

    monkeypatch.setattr(
        "backend.services.live_scoring_event_bus.publish_from_thread",
        lambda event: published.append(event),
    )

    def fake_ingest(**kwargs):
        return {
            "mode": "apply",
            "scoreboard_fingerprint": "xyz",
            "game_states": {"401": "live"},
            "change_detected": True,
            "downstream_updates_triggered": True,
            "matchup_projection_snapshots": [],
        }

    monkeypatch.setattr(polling, "_run_ingest", fake_ingest, raising=False)
    monkeypatch.setattr(
        "backend.services.live_scoring_ingest_service.run_live_scoreboard_ingest_with_controls",
        fake_ingest,
    )

    with polling._runtime_lock:
        polling._RUNTIME_STATE.clear()

    import os
    monkeypatch.setenv("LIVE_SCORING_POLL_YEAR", "2026")
    monkeypatch.setenv("LIVE_SCORING_POLL_WEEK", "14")

    # Patch the actual ingest call inside run_live_scoring_poll_cycle
    import unittest.mock as mock

    with mock.patch(
        "backend.services.live_scoring_polling_service.run_live_scoreboard_ingest_with_controls",
        side_effect=fake_ingest,
    ):
        result = polling.run_live_scoring_poll_cycle()

    assert result["status"] == "success"
    assert len(published) == 1
    assert published[0]["event"] == "score_update"
    assert published[0]["week"] == 14


def test_poll_cycle_does_not_publish_when_no_change(monkeypatch):
    """When mode is apply_skipped (no change), publish_from_thread is NOT called."""
    from backend.services import live_scoring_polling_service as polling

    published = []

    monkeypatch.setattr(
        "backend.services.live_scoring_event_bus.publish_from_thread",
        lambda event: published.append(event),
    )

    def fake_ingest_skipped(**kwargs):
        return {
            "mode": "apply_skipped",
            "scoreboard_fingerprint": "xyz",
            "game_states": {"401": "live"},
            "change_detected": False,
            "downstream_updates_triggered": False,
            "matchup_projection_snapshots": [],
        }

    import unittest.mock as mock

    monkeypatch.setenv("LIVE_SCORING_POLL_YEAR", "2026")
    monkeypatch.setenv("LIVE_SCORING_POLL_WEEK", "14")

    with mock.patch(
        "backend.services.live_scoring_polling_service.run_live_scoreboard_ingest_with_controls",
        side_effect=fake_ingest_skipped,
    ):
        result = polling.run_live_scoring_poll_cycle()

    assert result["status"] == "success"
    assert published == []
