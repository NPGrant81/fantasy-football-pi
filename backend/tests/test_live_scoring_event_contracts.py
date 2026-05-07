import json
from pathlib import Path

from backend.services.live_scoring_contract import (
    inspect_play_by_play_contract,
    inspect_summary_contract,
)
from backend.services.live_scoring_ingest_service import inspect_event_contracts


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "live_scoring"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_summary_fixture_passes_required_paths_contract_gate():
    payload = _load_fixture("summary_contract_fixture.json")
    report = inspect_summary_contract(payload)
    assert report.missing_paths == []


def test_play_by_play_fixture_passes_required_paths_contract_gate():
    payload = _load_fixture("play_by_play_contract_fixture.json")
    report = inspect_play_by_play_contract(payload)
    assert report.missing_paths == []


def test_inspect_event_contracts_combines_summary_and_play_by_play(monkeypatch):
    summary_payload = _load_fixture("summary_contract_fixture.json")
    pbp_payload = _load_fixture("play_by_play_contract_fixture.json")

    def fake_fetch_summary(event_id: str, timeout_seconds: int = 30, override_url=None):
        return summary_payload, {
            "source": "espn_summary_primary",
            "event_id": event_id,
            "status": "success",
        }

    def fake_fetch_pbp(event_id: str, timeout_seconds: int = 30, override_url=None):
        return pbp_payload, {
            "source": "espn_play_by_play_primary",
            "event_id": event_id,
            "status": "success",
        }

    monkeypatch.setattr(
        "backend.services.live_scoring_ingest_service.fetch_summary_payload_with_diagnostics",
        fake_fetch_summary,
    )
    monkeypatch.setattr(
        "backend.services.live_scoring_ingest_service.fetch_play_by_play_payload_with_diagnostics",
        fake_fetch_pbp,
    )

    result = inspect_event_contracts("401772001")
    assert result["degraded"] is False
    assert result["summary"]["missing_required_paths_count"] == 0
    assert result["play_by_play"]["missing_required_paths_count"] == 0
