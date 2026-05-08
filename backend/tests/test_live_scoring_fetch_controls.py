import json
import os
from pathlib import Path
import time

from backend.services import live_scoring_ingest_service as ingest


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._payload


def test_scoreboard_fetch_uses_cache(monkeypatch):
    calls = []

    def fake_get(url, timeout=30):
        calls.append((url, timeout))
        return _FakeResponse({"events": [{"id": "401772001", "competitions": []}]})

    monkeypatch.setenv("LIVE_SCORING_CACHE_TTL_SECONDS", "60")
    monkeypatch.setattr(ingest.requests, "get", fake_get)

    ingest._FETCH_CACHE.clear()

    _, first_diag = ingest.fetch_scoreboard_payload_with_diagnostics(2026, week=1)
    _, second_diag = ingest.fetch_scoreboard_payload_with_diagnostics(2026, week=1)

    assert len(calls) == 1
    assert first_diag["mode"] == "live_fetch"
    assert first_diag["cache_hit"] is False
    assert second_diag["mode"] == "cache"
    assert second_diag["cache_hit"] is True


def test_summary_fetch_persists_raw_payload_snapshot(monkeypatch, tmp_path):
    payload = {"header": {"id": "401772001", "competitions": [], "season": {"year": 2026}}}

    def fake_get(url, timeout=30):
        return _FakeResponse(payload)

    monkeypatch.setenv("LIVE_SCORING_STORE_RAW_RESPONSES", "1")
    monkeypatch.setenv("LIVE_SCORING_RAW_RESPONSE_DIR", str(tmp_path))
    monkeypatch.setenv("LIVE_SCORING_CACHE_TTL_SECONDS", "0")
    monkeypatch.setattr(ingest.requests, "get", fake_get)

    _, diagnostics = ingest.fetch_summary_payload_with_diagnostics("401772001")
    raw_path = diagnostics.get("raw_response_path")

    assert raw_path is not None
    stored = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    assert stored["header"]["id"] == "401772001"


def test_rate_limit_sleeps_between_same_source_calls(monkeypatch):
    sleep_calls = []
    calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    def fake_get(url, timeout=30):
        calls.append(url)
        return _FakeResponse({"header": {"id": "401772001", "competitions": [], "season": {"year": 2026}}})

    monkeypatch.setenv("LIVE_SCORING_RATE_LIMIT_SECONDS", "0.5")
    monkeypatch.setenv("LIVE_SCORING_CACHE_TTL_SECONDS", "0")
    monkeypatch.setattr(ingest.time, "sleep", fake_sleep)
    monkeypatch.setattr(ingest.requests, "get", fake_get)

    ingest._REQUEST_LAST_CALL_TS.clear()

    ingest.fetch_summary_payload_with_diagnostics("401772001")
    ingest.fetch_summary_payload_with_diagnostics("401772001")

    assert len(calls) == 2
    assert sleep_calls, "Expected at least one rate-limit sleep"


def test_raw_snapshot_retention_prunes_to_max_files(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_SCORING_RAW_RESPONSE_MAX_FILES", "2")
    monkeypatch.setenv("LIVE_SCORING_RAW_RESPONSE_MAX_AGE_SECONDS", "0")

    for idx in range(4):
        path = tmp_path / f"s{idx}.json"
        path.write_text(json.dumps({"idx": idx}), encoding="utf-8")
        ts = time.time() - (100 - idx)
        os.utime(path, (ts, ts))

    result = ingest._prune_raw_payload_snapshots(tmp_path)

    remaining = sorted(path.name for path in tmp_path.glob("*.json"))
    assert result["deleted_for_count"] == 2
    assert len(remaining) == 2


def test_raw_snapshot_retention_prunes_by_age(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_SCORING_RAW_RESPONSE_MAX_FILES", "0")
    monkeypatch.setenv("LIVE_SCORING_RAW_RESPONSE_MAX_AGE_SECONDS", "5")

    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text("{}", encoding="utf-8")
    new_path.write_text("{}", encoding="utf-8")

    old_ts = time.time() - 30
    now_ts = time.time()
    os.utime(old_path, (old_ts, old_ts))
    os.utime(new_path, (now_ts, now_ts))

    result = ingest._prune_raw_payload_snapshots(tmp_path)

    assert result["deleted_for_age"] == 1
    assert not old_path.exists()
    assert new_path.exists()
