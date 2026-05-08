from backend.services import live_scoring_polling_service as polling


def test_detect_state_transitions_tracks_phase_changes():
    transitions = polling._detect_state_transitions(
        {"401": "pre", "402": "live"},
        {"401": "live", "402": "final", "403": "pre"},
    )

    assert transitions == [
        {"event_id": "401", "from": "pre", "to": "live"},
        {"event_id": "402", "from": "live", "to": "final"},
        {"event_id": "403", "from": "unknown", "to": "pre"},
    ]


def test_poll_cycle_passes_previous_fingerprint_to_change_guard(monkeypatch):
    calls = []

    def fake_ingest(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            assert kwargs["change_guard_fingerprint"] is None
            return {
                "mode": "apply",
                "scoreboard_fingerprint": "abc",
                "game_states": {"401": "pre"},
                "change_detected": True,
                "downstream_updates_triggered": True,
            }

        assert kwargs["change_guard_fingerprint"] == "abc"
        return {
            "mode": "apply_skipped",
            "scoreboard_fingerprint": "abc",
            "game_states": {"401": "pre"},
            "change_detected": False,
            "downstream_updates_triggered": False,
        }

    monkeypatch.setenv("LIVE_SCORING_POLL_IDLE_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("LIVE_SCORING_POLL_ACTIVE_INTERVAL_SECONDS", "20")
    monkeypatch.setattr(polling, "run_live_scoreboard_ingest_with_controls", fake_ingest)

    polling._RUNTIME_STATE.clear()

    first = polling.run_live_scoring_poll_cycle(year=2026, week=1)
    assert first["mode"] == "apply"
    assert first["downstream_updates_triggered"] is True

    polling._RUNTIME_STATE["2026:1"]["last_polled_epoch"] = 0.0

    second = polling.run_live_scoring_poll_cycle(year=2026, week=1)
    assert second["mode"] == "apply_skipped"
    assert second["downstream_updates_triggered"] is False


def test_poll_cycle_interval_gate_skips_when_too_soon(monkeypatch):
    polling._RUNTIME_STATE.clear()
    polling._RUNTIME_STATE["2026:1"] = {
        "fingerprint": "abc",
        "game_states": {"401": "pre"},
        "last_polled_epoch": 100.0,
    }

    monkeypatch.setenv("LIVE_SCORING_POLL_IDLE_INTERVAL_SECONDS", "90")
    monkeypatch.setenv("LIVE_SCORING_POLL_ACTIVE_INTERVAL_SECONDS", "20")
    monkeypatch.setattr(polling.time, "time", lambda: 120.0)

    result = polling.run_live_scoring_poll_cycle(year=2026, week=1)

    assert result["status"] == "skipped"
    assert result["reason"] == "interval_gate"
    assert result["downstream_updates_triggered"] is False


def test_get_poll_runtime_status_reflects_state(monkeypatch):
    polling._RUNTIME_STATE.clear()
    polling._RUNTIME_STATE["2026:1"] = {"last_mode": "apply"}

    status = polling.get_poll_runtime_status()

    assert "2026:1" in status["keys"]
    assert status["state"]["2026:1"]["last_mode"] == "apply"


def test_load_recent_poll_cycles_reads_jsonl(monkeypatch, tmp_path):
    path = tmp_path / "poll_cycles.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"status":"success","week":1}',
                '{"status":"skipped","week":1}',
                '{"status":"failed","week":1}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(polling, "CYCLE_LOG_PATH", path)

    rows = polling.load_recent_poll_cycles(limit=2)
    assert len(rows) == 2
    assert rows[0]["status"] == "skipped"
    assert rows[1]["status"] == "failed"


def test_summarize_poll_cycles_counts_statuses(monkeypatch, tmp_path):
    path = tmp_path / "poll_cycles.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"status":"success","mode":"apply"}',
                '{"status":"success","mode":"apply_skipped"}',
                '{"status":"skipped"}',
                '{"status":"failed"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(polling, "CYCLE_LOG_PATH", path)

    summary = polling.summarize_poll_cycles(limit=10)
    assert summary["cycles_considered"] == 4
    assert summary["status_counts"]["success"] == 2
    assert summary["status_counts"]["skipped"] == 1
    assert summary["status_counts"]["failed"] == 1
    assert summary["mode_counts"]["apply"] == 1
    assert summary["mode_counts"]["apply_skipped"] == 1
