from copy import deepcopy
import csv
import hashlib
import json

import pytest

from backend.scripts import reconcile_ppl_mfl_sources as script


@pytest.fixture
def source_evidence():
    return {
        "season": 2024,
        "sources": {
            "players.csv": [
                {"Player_ID": "10", "PlayerName": "Brown, AJ", "PositionID": "2"}
            ],
            "positions.csv": [{"PositionID": "2", "Position": "WR"}],
            "users.csv": [{"OwnerID": "1", "OwnerName": "Private Owner"}],
            "draft_results.csv": [
                {
                    "Year": "2024",
                    "OwnerID": "1",
                    "PlayerID": "10",
                    "PositionID": "2",
                    "TeamID": "3",
                    "WinningBid": "5.01",
                }
            ],
        },
        "players": [
            {"player_mfl_id": "123", "player_name": "AJ Brown", "position": "WR"}
        ],
        "franchises": [{"franchise_id": "0001", "owner_email": "private@example.test"}],
        "drafts": [
            {
                "player_mfl_id": "123",
                "franchise_id": "0001",
                "winning_bid": "5.01",
                "draft_source": "auctionResults",
                "draft_style": "auction",
            }
        ],
        "draft_sha256": "a" * 64,
    }


def test_source_comparison_is_unapproved_and_preserves_ids_and_inputs(source_evidence):
    before = deepcopy(source_evidence)
    report = script.reconcile_season(**source_evidence)
    assert report["approved"] is False
    assert report["legacy_status_counts"] == {"single_candidate_review": 1}
    assert report["native_status_counts"] == {"single_candidate_review": 1}
    assert report["native_events"][0]["franchise_id"] == "0001"
    assert report["native_events"][0]["winning_bid"] == "5.01"
    assert report["native_events"][0]["evidence_ref"] == "a" * 64 + ":2"
    assert report["source_owner_franchise_candidates"][0]["approved"] is False
    assert source_evidence == before
    assert "Brown" not in str(report)
    assert "Private Owner" not in str(report)
    assert "private@example" not in str(report)


def test_conflicting_legacy_player_ids_are_not_resolved_by_matching_name(
    source_evidence,
):
    source_evidence["sources"]["players.csv"].append(
        {"Player_ID": "10", "PlayerName": "Other Player", "PositionID": "2"}
    )
    report = script.reconcile_season(**source_evidence)
    assert report["legacy_status_counts"] == {"unverified_legacy_identity": 1}
    assert report["native_status_counts"] == {"no_legacy_candidate": 1}
    assert report["source_owner_franchise_candidates"] == []


def test_source_comparison_does_not_round_bid_or_guess_position(source_evidence):
    source_evidence["drafts"][0]["winning_bid"] = "5.01001"
    report = script.reconcile_season(**source_evidence)
    assert report["legacy_status_counts"] == {"no_candidate": 1}
    source_evidence["sources"]["draft_results.csv"][0]["PositionID"] = ""
    report = script.reconcile_season(**source_evidence)
    assert report["legacy_status_counts"] == {"unverified_legacy_identity": 1}


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"player_mfl_id": "999"}, "missing_or_conflicting_native_player"),
        ({"franchise_id": "999"}, "missing_native_franchise"),
        ({"winning_bid": ""}, "missing_or_invalid_bid"),
        ({"draft_style": "snake"}, "unsupported_draft_grain"),
    ],
)
def test_invalid_source_events_remain_explicitly_blocked(
    source_evidence, change, reason
):
    source_evidence["drafts"][0].update(change)
    report = script.reconcile_season(**source_evidence)
    assert report["native_events"][0]["status"] == "blocked"
    assert reason in report["blockers"][0]["reasons"]
    assert report["source_owner_franchise_candidates"] == []


def test_repeated_native_event_tuples_preserve_all_rows(source_evidence):
    source_evidence["drafts"] *= 2
    report = script.reconcile_season(**source_evidence)
    assert report["native_draft_rows"] == 2
    assert report["legacy_status_counts"] == {"ambiguous": 1}
    assert report["blockers"] == [
        {
            "kind": "repeated_native_event_tuple_requires_grain_review",
            "additional_rows": 1,
        }
    ]


def test_conflicting_native_catalog_is_not_used_for_candidates(source_evidence):
    source_evidence["players"].append(
        {"player_mfl_id": "123", "player_name": "Other Player", "position": "WR"}
    )
    report = script.reconcile_season(**source_evidence)
    assert report["native_events"][0]["status"] == "blocked"
    assert report["legacy_status_counts"] == {"no_candidate": 1}


def test_empty_source_export_is_not_certified_as_complete(source_evidence):
    source_evidence["drafts"] = []
    report = script.reconcile_season(**source_evidence)
    assert report["blockers"] == [{"kind": "empty_source_export_requires_review"}]
    assert report["approved"] is False


def test_source_owner_candidates_do_not_leak_between_seasons(source_evidence):
    source_evidence["season"] = 2023
    report = script.reconcile_season(**source_evidence)
    assert report["legacy_draft_rows"] == 0
    assert report["source_owner_franchise_candidates"] == []


def test_native_mapping_template_covers_franchises_without_legacy_matches(
    source_evidence,
):
    source_evidence["sources"]["draft_results.csv"][0]["PositionID"] = ""
    source_evidence["franchises"].append({"franchise_id": "0002"})
    report = script.reconcile_season(**source_evidence)
    template = report["native_mapping_review_template"]
    assert template["approved"] is False
    assert template["franchises"] == [
        {"franchise_id": "0001", "target_owner_id": None, "evidence": []},
        {"franchise_id": "0002", "target_owner_id": None, "evidence": []},
    ]
    assert template["drafted_players"] == [
        {"player_mfl_id": "123", "target_player_id": None, "evidence": []}
    ]


def test_split_owner_evidence_is_not_resolved_by_majority(source_evidence):
    source_evidence["franchises"].append({"franchise_id": "0002"})
    source_evidence["drafts"].append(
        {**source_evidence["drafts"][0], "franchise_id": "0002", "winning_bid": "6"}
    )
    source_evidence["sources"]["draft_results.csv"].extend(
        [
            {**source_evidence["sources"]["draft_results.csv"][0], "WinningBid": "6"},
            deepcopy(source_evidence["sources"]["draft_results.csv"][0]),
        ]
    )
    report = script.reconcile_season(**source_evidence)
    assert report["source_owner_conflicts"]["split_legacy_owners"] == [
        {"source_owner_id": 1, "candidate_franchise_ids": ["0001", "0002"]}
    ]
    assert {"kind": "conflicting_season_owner_evidence"} in report["blockers"]
    assert all(
        candidate["approved"] is False
        for candidate in report["source_owner_franchise_candidates"]
    )


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def selected_exports(tmp_path, source_evidence):
    source_root = tmp_path / "legacy"
    export_root = tmp_path / "mfl"
    for name, rows in source_evidence["sources"].items():
        _write_csv(source_root / name, rows)
    for report, key in (
        ("players", "players"),
        ("franchises", "franchises"),
        ("draftResults", "drafts"),
    ):
        rows = [
            {
                **row,
                "season": "2024",
                "league_id": "11422",
                "source_system": "mfl",
                "source_endpoint": report,
                "extracted_at_utc": "2026-11-01T00:00:00Z",
            }
            for row in source_evidence[key]
        ]
        _write_csv(export_root / report / "2024.csv", rows)
    return source_root, export_root


def test_offline_cli_persists_hash_bound_worksheet_and_refuses_overwrite(
    tmp_path, selected_exports, monkeypatch
):
    import requests

    def unexpected_request(*args, **kwargs):
        pytest.fail("Offline source reconciliation must not make API calls.")

    monkeypatch.setattr(requests.sessions.Session, "request", unexpected_request)
    source_root, export_root = selected_exports
    output = tmp_path / "worksheet.json"
    args = [
        "--source-root",
        str(source_root),
        "--season-export",
        f"2024={export_root}",
        "--output",
        str(output),
    ]
    assert script.main(args) == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["ready_to_import"] is False
    assert report["api_requests_sent"] == 0
    assert report["writes_performed_to_databases"] is False
    digest = hashlib.sha256(
        (export_root / "draftResults" / "2024.csv").read_bytes()
    ).hexdigest()
    assert report["seasons"][0]["native_events"][0]["evidence_ref"] == f"{digest}:2"
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        script.main(args)
    assert output.read_bytes() == original


@pytest.mark.parametrize(
    "column,value",
    [
        ("season", "2023"),
        ("league_id", "38909"),
        ("source_system", "other"),
        ("source_endpoint", "transactions"),
        ("extracted_at_utc", ""),
    ],
)
def test_selected_exports_reject_conflicting_provenance(
    selected_exports, column, value
):
    source_root, export_root = selected_exports
    path = export_root / "draftResults" / "2024.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0][column] = value
    _write_csv(path, rows)
    with pytest.raises(ValueError, match="conflicting provenance"):
        script.run_source_reconciliation(
            source_root=source_root,
            season_exports={2024: export_root},
            draft_exports={},
        )


def test_draft_override_is_explicit_and_hash_bound(tmp_path, selected_exports):
    source_root, export_root = selected_exports
    path = export_root / "draftResults" / "2024.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["winning_bid"] = "6"
    override = tmp_path / "fresh.csv"
    _write_csv(override, rows)
    report = script.run_source_reconciliation(
        source_root=source_root,
        season_exports={2024: export_root},
        draft_exports={2024: override},
    )
    assert report["seasons"][0]["native_events"][0]["winning_bid"] == "6"
    assert (
        report["selected_mfl_exports"][-1]["sha256"]
        == hashlib.sha256(override.read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("selection", [["2024"], ["2024="], ["2024=a", "2024=b"]])
def test_duplicate_or_malformed_selections_are_rejected(selection):
    with pytest.raises(ValueError):
        script._selections(selection)
