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


def test_conflict_register_retains_every_variant_and_duplicate_row(source_evidence):
    sources = source_evidence["sources"]
    original = deepcopy(sources["players.csv"][0])
    sources["players.csv"].extend(
        [
            {**original, "PlayerName": "Other Player"},
            original,
        ]
    )
    sources["users.csv"].append({"OwnerID": "1", "OwnerName": "Other Owner"})
    hashes = {name: "a" * 64 for name in sources}
    report = script._legacy_conflict_register(sources, hashes)
    assert len(report) == 2
    player = report[0]
    assert player["source_id"] == 10
    assert player["differing_columns"] == ["PlayerName"]
    assert len(player["variants"]) == 2
    assert player["variants"][0]["source_row_refs"] == [
        "a" * 64 + ":2",
        "a" * 64 + ":4",
    ]
    assert all(row["approved"] is False and row["resolution"] is None for row in report)
    assert "Other Player" not in str(report)
    assert "Other Owner" not in str(report)


def test_source_comparison_does_not_round_bid_or_guess_position(source_evidence):
    source_evidence["drafts"][0]["winning_bid"] = "5.01001"
    report = script.reconcile_season(**source_evidence)
    assert report["legacy_status_counts"] == {"no_candidate": 1}
    source_evidence["sources"]["draft_results.csv"][0]["PositionID"] = ""
    report = script.reconcile_season(**source_evidence)
    assert report["legacy_status_counts"] == {"unverified_legacy_identity": 1}


@pytest.fixture
def conflicting_player_evidence(source_evidence):
    source_evidence["sources"]["players.csv"].append(
        {"Player_ID": "10", "PlayerName": "Other Player", "PositionID": "3"}
    )
    source_evidence["players"].append(
        {"player_mfl_id": "124", "player_name": "Other Player", "position": "RB"}
    )
    return source_evidence


def test_player_conflicts_preserve_all_variants_and_exact_event_evidence(
    conflicting_player_evidence,
):
    before = deepcopy(conflicting_player_evidence)
    report = script.reconcile_season(**conflicting_player_evidence)
    profile = report["player_conflict_audit"][0]
    assert profile["source_player_id"] == 10
    assert len(profile["variants"]) == 2
    assert all(v["status"] == "single_native_id_review" for v in profile["variants"])
    event = profile["affected_draft_rows"][0]
    assert event["status"] == "single_event_review"
    assert event["candidate_native_events"][0]["player_mfl_id"] == "123"
    assert len(event["candidate_native_events"][0]["supporting_variant_sha256"]) == 1
    assert event["approved"] is False and event["resolution"] is None
    assert conflicting_player_evidence == before
    assert "Brown" not in str(profile)
    assert "Other Player" not in str(profile)


def test_player_conflict_audit_does_not_guess_when_two_variants_match_bid(
    conflicting_player_evidence,
):
    conflicting_player_evidence["drafts"].append(
        {**conflicting_player_evidence["drafts"][0], "player_mfl_id": "124"}
    )
    report = script.reconcile_season(**conflicting_player_evidence)
    event = report["player_conflict_audit"][0]["affected_draft_rows"][0]
    assert event["status"] == "ambiguous"
    assert len(event["candidate_native_events"]) == 2
    dispositions = script._player_conflict_dispositions(
        conflicting_player_evidence["sources"], [report]
    )
    assert dispositions[0]["disposition"] == "blocked_ambiguous_or_missing_event"


def test_player_dispositions_require_row_specific_identity_for_reused_ids(
    conflicting_player_evidence,
):
    conflicting_player_evidence["sources"]["draft_results.csv"].append(
        {
            **conflicting_player_evidence["sources"]["draft_results.csv"][0],
            "WinningBid": "6",
        }
    )
    conflicting_player_evidence["drafts"].append(
        {
            **conflicting_player_evidence["drafts"][0],
            "player_mfl_id": "124",
            "winning_bid": "6",
        }
    )
    report = script.reconcile_season(**conflicting_player_evidence)
    disposition = script._player_conflict_dispositions(
        conflicting_player_evidence["sources"], [report]
    )[0]
    assert disposition["single_event_candidate_native_ids"] == ["123", "124"]
    assert disposition["row_specific_identity_required"] is True
    assert disposition["disposition"] == "event_resolutions_ready_for_review"
    assert disposition["approved"] is False
    assert disposition["resolution"] is None


def test_missing_season_or_catalog_only_conflict_blocks_reconstruction(
    conflicting_player_evidence,
):
    report = script.reconcile_season(**conflicting_player_evidence)
    conflicting_player_evidence["sources"]["draft_results.csv"].append(
        {
            **conflicting_player_evidence["sources"]["draft_results.csv"][0],
            "Year": "2023",
        }
    )
    disposition = script._player_conflict_dispositions(
        conflicting_player_evidence["sources"], [report]
    )[0]
    assert disposition["uncovered_legacy_rows"] == [3]
    assert disposition["disposition"] == "blocked_missing_season_evidence"
    conflicting_player_evidence["sources"]["draft_results.csv"] = []
    report = script.reconcile_season(**conflicting_player_evidence)
    disposition = script._player_conflict_dispositions(
        conflicting_player_evidence["sources"], [report]
    )[0]
    assert disposition["disposition"] == "blocked_catalog_only_identity_review"


def test_player_audit_keeps_duplicate_rows_and_blank_names_blocked(
    conflicting_player_evidence,
):
    conflicting_player_evidence["sources"]["players.csv"][1]["PlayerName"] = " "
    conflicting_player_evidence["sources"]["players.csv"].append(
        deepcopy(conflicting_player_evidence["sources"]["players.csv"][0])
    )
    conflicting_player_evidence["drafts"] *= 2
    profile = script.reconcile_season(**conflicting_player_evidence)[
        "player_conflict_audit"
    ][0]
    assert sorted(len(v["legacy_catalog_rows"]) for v in profile["variants"]) == [1, 2]
    assert any(v["status"] == "missing_name" for v in profile["variants"])
    assert profile["affected_draft_rows"][0]["status"] == "ambiguous"


def test_suffix_aliases_share_candidates_without_becoming_approved(source_evidence):
    source_evidence["sources"]["players.csv"] = [
        {"Player_ID": "10", "PlayerName": "AJ Brown", "PositionID": "2"},
        {"Player_ID": "10", "PlayerName": "AJ Brown Jr.", "PositionID": "2"},
    ]
    profile = script.reconcile_season(**source_evidence)["player_conflict_audit"][0]
    assert profile["variant_relationship"] == "suffix_or_punctuation_alias_review"
    assert len(profile["variants"]) == 2
    assert all(v["status"] == "single_native_id_review" for v in profile["variants"])
    event = profile["affected_draft_rows"][0]
    assert len(event["candidate_native_events"]) == 1
    assert len(event["candidate_native_events"][0]["supporting_variant_sha256"]) == 2
    assert event["approved"] is False


def test_suffix_name_collision_remains_ambiguous(source_evidence):
    source_evidence["sources"]["players.csv"].append(
        {"Player_ID": "10", "PlayerName": "AJ Brown Jr.", "PositionID": "2"}
    )
    source_evidence["players"].append(
        {"player_mfl_id": "125", "player_name": "AJ Brown Sr.", "position": "WR"}
    )
    source_evidence["drafts"].append(
        {**source_evidence["drafts"][0], "player_mfl_id": "125"}
    )
    profile = script.reconcile_season(**source_evidence)["player_conflict_audit"][0]
    assert profile["affected_draft_rows"][0]["status"] == "ambiguous"
    assert all(v["status"] == "ambiguous" for v in profile["variants"])


@pytest.fixture
def disputed_position_evidence(source_evidence):
    source_evidence["sources"]["positions.csv"] = [
        {"PositionID": "8099", "Position": "Kicker"},
        {"PositionID": "8099", "Position": "PK"},
    ]
    source_evidence["sources"]["draft_results.csv"][0]["PositionID"] = "8099"
    source_evidence["sources"]["players.csv"][0]["PositionID"] = "8099"
    source_evidence["players"][0]["position"] = "Def"
    return source_evidence


def test_position_audit_does_not_use_disputed_position_to_filter_native_events(
    disputed_position_evidence,
):
    before = deepcopy(disputed_position_evidence)
    report = script.reconcile_season(**disputed_position_evidence)
    audit = report["position_conflict_audit"]
    assert audit["rows"][0]["candidate_native_positions"] == ["DST"]
    assert audit["rows"][0]["candidate_native_events"][0]["evidence_ref"] == (
        "a" * 64 + ":2"
    )
    assert audit["position_ids"] == [
        {
            "source_position_id": 8099,
            "affected_draft_rows": 1,
            "candidate_position_sets": [{"native_positions": ["DST"], "rows": 1}],
            "global_replacement_approved": False,
        }
    ]
    assert audit["rows"][0]["approved"] is False
    assert disputed_position_evidence == before
    assert "Brown" not in str(audit)


def test_position_audit_preserves_conflicting_player_variants_and_all_events(
    disputed_position_evidence,
):
    disputed_position_evidence["sources"]["players.csv"].append(
        {"Player_ID": "10", "PlayerName": "Other Player", "PositionID": "8099"}
    )
    disputed_position_evidence["players"].append(
        {"player_mfl_id": "124", "player_name": "Other Player", "position": "PK"}
    )
    disputed_position_evidence["drafts"].append(
        {**disputed_position_evidence["drafts"][0], "player_mfl_id": "124"}
    )
    audit = script.reconcile_season(**disputed_position_evidence)[
        "position_conflict_audit"
    ]
    assert audit["rows"][0]["candidate_native_positions"] == ["DST", "K"]
    assert len(audit["rows"][0]["candidate_native_events"]) == 2
    assert audit["rows"][0]["status"] == "ambiguous"


@pytest.mark.parametrize(
    "change",
    [
        {"winning_bid": "5.02"},
        {"winning_bid": ""},
        {"franchise_id": "999"},
        {"draft_style": "snake"},
    ],
)
def test_position_audit_does_not_use_invalid_or_inexact_source_events(
    disputed_position_evidence,
    change,
):
    disputed_position_evidence["drafts"][0].update(change)
    audit = script.reconcile_season(**disputed_position_evidence)[
        "position_conflict_audit"
    ]
    assert audit["rows"][0]["status"] == "no_candidate"
    assert audit["rows"][0]["candidate_native_events"] == []


def test_position_audit_is_season_scoped_and_counts_repeated_legacy_rows(
    disputed_position_evidence,
):
    rows = disputed_position_evidence["sources"]["draft_results.csv"]
    rows.extend([deepcopy(rows[0]), {**rows[0], "Year": "2023"}])
    audit = script.reconcile_season(**disputed_position_evidence)[
        "position_conflict_audit"
    ]
    assert len(audit["rows"]) == 2
    assert audit["position_ids"][0]["affected_draft_rows"] == 2
    assert [row["legacy_csv_row"] for row in audit["rows"]] == [2, 3]


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


def test_player_proposals_bind_legacy_and_native_catalog_rows_to_input_hashes(
    selected_exports,
):
    source_root, export_root = selected_exports
    path = source_root / "players.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.append({**rows[0], "PlayerName": "AJ Brown Jr."})
    _write_csv(path, rows)
    report = script.run_source_reconciliation(
        source_root=source_root, season_exports={2024: export_root}, draft_exports={}
    )
    profile = report["seasons"][0]["player_conflict_audit"][0]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert {
        ref for v in profile["variants"] for ref in v["legacy_catalog_row_refs"]
    } == {f"{digest}:2", f"{digest}:3"}
    native_digest = hashlib.sha256(
        (export_root / "players" / "2024.csv").read_bytes()
    ).hexdigest()
    assert all(
        c["evidence_ref"] == f"{native_digest}:2"
        for v in profile["variants"]
        for c in v["candidate_native_catalog"]
    )
    event = profile["affected_draft_rows"][0]
    assert event["legacy_evidence_ref"] == (
        report["legacy_source_files_sha256"]["draft_results.csv"] + ":2"
    )
    assert report["player_conflict_dispositions"][0]["reconstruction_blocked"] is True


@pytest.mark.parametrize("selection", [["2024"], ["2024="], ["2024=a", "2024=b"]])
def test_duplicate_or_malformed_selections_are_rejected(selection):
    with pytest.raises(ValueError):
        script._selections(selection)


@pytest.fixture
def approval_evidence(selected_exports):
    source_root, export_root = selected_exports
    path = source_root / "players.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.append({**rows[0], "PlayerName": "AJ Brown Jr."})
    _write_csv(path, rows)
    report = script.run_source_reconciliation(
        source_root=source_root, season_exports={2024: export_root}, draft_exports={}
    )
    decisions = {
        "approved": True,
        "review_basis": "Explicit reviewer identity and alias approval",
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
        "players": [
            {
                "source_player_id": 10,
                "player_mfl_id": "123",
                "native_position": "WR",
                "aliases_reviewed": True,
                "reviewed_variant_sha256": [
                    v["variant_sha256"]
                    for v in report["seasons"][0]["player_conflict_audit"][0][
                        "variants"
                    ]
                ],
            }
        ],
    }
    return report, decisions


@pytest.fixture
def owner_approval_evidence(approval_evidence):
    report, _ = deepcopy(approval_evidence)
    conflict = {
        "source_file": "users.csv",
        "source_id": 1,
        "variants": [{"variant_sha256": "variant-1"}, {"variant_sha256": "variant-2"}],
    }
    report["owner_conflict_audit"] = {
        "legacy_owner_conflicts": [conflict],
        "season_owner_entries": [
            {
                "season": 2024,
                "source_owner_id": 1,
                "source_owner_variant_refs": ["users-hash:2"],
                "candidate_franchises": [{"franchise_id": "0001"}],
                "draft_rows": [
                    {
                        "status": "single_event_review",
                        "legacy_evidence_ref": "draft-hash:2",
                        "candidate_native_events": [
                            {
                                "evidence_ref": "native-hash:2",
                                "franchise_id": "0001",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    decisions = {
        "approved": True,
        "review_basis": "Explicit source ownership review",
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
        "reviewed_owner_variant_sha256": ["variant-1", "variant-2"],
        "season_owners": [
            {
                "season": 2024,
                "source_owner_id": 1,
                "franchise_id": "0001",
                "approved": True,
            }
        ],
        "event_owner_exceptions": [],
    }
    return report, decisions


def test_owner_approval_resolves_source_ownership_not_target_accounts(
    owner_approval_evidence,
):
    report, decisions = owner_approval_evidence
    before = deepcopy(report)
    result = script.approve_owner_resolutions(report, decisions)
    assert result["ready_for_slice_4"] is True
    assert result["ready_to_import"] is False
    assert result["scope"] == "legacy_source_ownership_only_not_target_accounts"
    assert result["resolved_event_owners"][0]["franchise_id"] == "0001"
    assert report == before


@pytest.mark.parametrize(
    "failure",
    [
        "stale_hash",
        "missing_variant",
        "duplicate_mapping",
        "missing_mapping",
        "unsupported_franchise",
        "ambiguous_event",
        "unknown_exception",
        "unapproved",
    ],
)
def test_owner_approval_rejects_missing_or_conflicting_evidence(
    owner_approval_evidence, failure
):
    report, decisions = deepcopy(owner_approval_evidence)
    if failure == "stale_hash":
        decisions["legacy_source_files_sha256"] = {}
    elif failure == "missing_variant":
        decisions["reviewed_owner_variant_sha256"].pop()
    elif failure == "duplicate_mapping":
        decisions["season_owners"] *= 2
    elif failure == "missing_mapping":
        decisions["season_owners"] = []
    elif failure == "unsupported_franchise":
        decisions["season_owners"][0]["franchise_id"] = "0002"
    elif failure == "ambiguous_event":
        report["owner_conflict_audit"]["season_owner_entries"][0]["draft_rows"][0][
            "status"
        ] = "ambiguous"
    elif failure == "unknown_exception":
        decisions["event_owner_exceptions"] = [
            {
                "approved": True,
                "legacy_evidence_ref": "unknown",
            }
        ]
    else:
        decisions["approved"] = False
    with pytest.raises(ValueError):
        script.approve_owner_resolutions(report, decisions)


def test_owner_exception_is_row_specific_and_same_season(owner_approval_evidence):
    report, decisions = deepcopy(owner_approval_evidence)
    first = report["owner_conflict_audit"]["season_owner_entries"][0]
    second = deepcopy(first)
    second["source_owner_id"] = 2
    second["candidate_franchises"] = [{"franchise_id": "0002"}]
    second["draft_rows"][0]["legacy_evidence_ref"] = "draft-hash:3"
    second["draft_rows"][0]["candidate_native_events"][0] = {
        "evidence_ref": "native-hash:3",
        "franchise_id": "0002",
    }
    first["candidate_franchises"].append({"franchise_id": "0002"})
    first["draft_rows"][0]["candidate_native_events"][0]["franchise_id"] = "0002"
    report["owner_conflict_audit"]["season_owner_entries"].append(second)
    decisions["season_owners"].append(
        {
            **decisions["season_owners"][0],
            "source_owner_id": 2,
            "franchise_id": "0002",
        }
    )
    decisions["event_owner_exceptions"] = [
        {
            "approved": True,
            "legacy_evidence_ref": "draft-hash:2",
            "native_evidence_ref": "native-hash:2",
            "resolved_source_owner_id": 2,
        }
    ]
    result = script.approve_owner_resolutions(report, decisions)
    assert result["resolved_event_owners"][0]["original_source_owner_id"] == 1
    assert result["resolved_event_owners"][0]["resolved_source_owner_id"] == 2
    assert result["resolved_event_owners"][1]["resolved_source_owner_id"] == 2
    decisions["event_owner_exceptions"][0]["native_evidence_ref"] = "stale"
    with pytest.raises(ValueError, match="stale"):
        script.approve_owner_resolutions(report, decisions)


def test_duplicate_native_event_claims_are_blocked(owner_approval_evidence):
    report, decisions = deepcopy(owner_approval_evidence)
    rows = report["owner_conflict_audit"]["season_owner_entries"][0]["draft_rows"]
    rows.append({**rows[0], "legacy_evidence_ref": "draft-hash:3"})
    with pytest.raises(ValueError, match="same native event"):
        script.approve_owner_resolutions(report, decisions)


def test_owner_audit_requires_same_season_and_preserves_split_evidence(source_evidence):
    before = deepcopy(source_evidence)
    sources = source_evidence["sources"]
    sources["draft_results.csv"].extend(
        [
            {**sources["draft_results.csv"][0], "WinningBid": "6"},
            {**sources["draft_results.csv"][0], "Year": "2023"},
        ]
    )
    source_evidence["franchises"].append({"franchise_id": "0002"})
    source_evidence["drafts"].append(
        {
            **source_evidence["drafts"][0],
            "franchise_id": "0002",
            "winning_bid": "6",
        }
    )
    season = script.reconcile_season(**source_evidence)
    report = {
        "seasons": [season],
        "legacy_source_files_sha256": {"users.csv": "u", "draft_results.csv": "d"},
        "legacy_conflict_register": [],
    }
    audit = script._owner_conflict_audit(
        sources=sources,
        report=report,
        native_seasons={2024: {"players": source_evidence["players"]}},
        approved_players={"resolved_players": []},
    )
    assert len(audit["season_owner_entries"]) == 2
    assert (
        audit["season_owner_entries"][0]["draft_rows"][0]["status"]
        == "missing_season_evidence"
    )
    assert audit["season_owner_entries"][1]["status"] == "split_owner_evidence"
    assert audit["ready_for_slice_4"] is False
    assert before["sources"]["users.csv"] == sources["users.csv"]


@pytest.mark.parametrize("failure", ["unapproved", "stale", "unsupported", "duplicate"])
def test_supplemental_event_identity_requires_review_and_native_support(
    source_evidence, failure
):
    season = script.reconcile_season(**source_evidence)
    report = {
        "seasons": [season],
        "legacy_source_files_sha256": {"users.csv": "u", "draft_results.csv": "d"},
        "legacy_conflict_register": [],
    }
    entry = {
        "legacy_csv_row": 2,
        "legacy_evidence_ref": "d:2",
        "player_mfl_id": "123",
        "approved": True,
    }
    if failure == "unapproved":
        entry["approved"] = False
    elif failure == "stale":
        entry["legacy_evidence_ref"] = "old:2"
    elif failure == "unsupported":
        entry["player_mfl_id"] = "999"
    entries = [entry, deepcopy(entry)] if failure == "duplicate" else [entry]
    with pytest.raises(ValueError):
        script._owner_conflict_audit(
            sources=source_evidence["sources"],
            report=report,
            native_seasons={2024: {"players": source_evidence["players"]}},
            approved_players={"resolved_players": []},
            reviewed_event_identities=entries,
        )


def test_owner_cli_replays_full_source_approval_without_network_or_database(
    selected_exports,
    approval_evidence,
    tmp_path,
    capsys,
    monkeypatch,
):
    import requests

    def unexpected(*args, **kwargs):
        pytest.fail("Owner approval must remain offline.")

    monkeypatch.setattr(requests.sessions.Session, "request", unexpected)
    source_root, export_root = selected_exports
    _, players = approval_evidence
    report = script.run_source_reconciliation(
        source_root=source_root,
        season_exports={2024: export_root},
        draft_exports={},
        player_resolutions=players,
    )
    owners = {
        "approved": True,
        "review_basis": "Explicit per-season ownership approval",
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
        "reviewed_owner_variant_sha256": [],
        "event_owner_exceptions": [],
        "season_owners": [
            {
                "season": 2024,
                "source_owner_id": 1,
                "franchise_id": "0001",
                "approved": True,
            }
        ],
    }
    player_path, owner_path = tmp_path / "players.json", tmp_path / "owners.json"
    player_path.write_text(json.dumps(players), encoding="utf-8")
    owner_path.write_text(json.dumps(owners), encoding="utf-8")
    output = tmp_path / "reviewed.json"
    assert (
        script.main(
            [
                "--source-root",
                str(source_root),
                "--season-export",
                f"2024={export_root}",
                "--player-resolutions",
                str(player_path),
                "--owner-resolutions",
                str(owner_path),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    saved = json.loads(output.read_text())
    assert saved["approved_owner_resolutions"]["ready_for_slice_4"] is True
    assert saved["ready_to_import"] is False
    assert "Slice 4 ready" in capsys.readouterr().out


def test_explicit_approval_resolves_identities_not_import_or_positions(
    approval_evidence,
):
    report, decisions = approval_evidence
    before = deepcopy(report)
    result = script.approve_player_resolutions(report, decisions)
    assert result["player_identity_gate"] == "resolved"
    assert result["ready_for_slice_3"] is True
    assert result["ready_to_import"] is False
    assert result["resolved_players"][0]["scope"] == "legacy_player_identity_only"
    assert len(result["resolved_players"][0]["catalog_evidence_refs"]) == 1
    assert len(result["resolved_players"][0]["native_event_refs"]) == 1
    assert report == before


def test_attribute_cli_replays_reviewed_repairs_and_preserves_input_files(
    selected_exports, tmp_path, monkeypatch, capsys
):
    import requests

    def unexpected(*args, **kwargs):
        pytest.fail("Attribute reconciliation must remain offline.")

    monkeypatch.setattr(requests.sessions.Session, "request", unexpected)
    source_root, export_root = selected_exports
    _write_csv(source_root / "teams.csv", [{"Team": "PHI", "TeamID": "3"}])
    path = export_root / "players" / "2024.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    _write_csv(path, [{**row, "nfl_team": "PHI"} for row in rows])
    path = export_root / "draftResults" / "2024.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["raw_pick"] = json.dumps(
            {
                "player": row["player_mfl_id"],
                "franchise": row["franchise_id"],
                "cost": row["winning_bid"],
                "source": "auctionResults",
                "timestamp": "1724684051",
            }
        )
    _write_csv(path, rows)
    report = script.run_source_reconciliation(
        source_root=source_root, season_exports={2024: export_root}, draft_exports={}
    )
    common = {
        "approved": True,
        "review_basis": "Explicit fixture review",
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
    }
    players = {**common, "players": []}
    owners = {
        **common,
        "reviewed_owner_variant_sha256": [],
        "season_owners": [
            {
                "season": 2024,
                "source_owner_id": 1,
                "franchise_id": "0001",
                "approved": True,
            }
        ],
    }
    report = script.run_source_reconciliation(
        source_root=source_root,
        season_exports={2024: export_root},
        draft_exports={},
        player_resolutions=players,
        owner_resolutions=owners,
        audit_attributes=True,
    )
    audit = report["attribute_repair_audit"]
    attributes = {
        **common,
        "teams_sha256": audit["teams_sha256"],
        "taxonomy": audit["taxonomy_proposals"],
        "draft_rows": [row["proposal"] for row in audit["draft_rows"]],
        "catalog_positions": [
            row["proposal"] for row in audit["catalog_rows"] if row["proposal"]
        ],
    }
    args = [
        "--source-root",
        str(source_root),
        "--season-export",
        f"2024={export_root}",
        "--output",
        str(tmp_path / "resolved.json"),
    ]
    for flag, manifest in (
        ("player", players),
        ("owner", owners),
        ("attribute", attributes),
    ):
        path = tmp_path / f"{flag}.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        args += [f"--{flag}-resolutions", str(path)]
    inputs = {path: path.read_bytes() for path in tmp_path.rglob("*.csv")}
    assert script.main(args) == 2
    saved = json.loads((tmp_path / "resolved.json").read_text())
    assert saved["approved_attribute_resolutions"]["ready_for_slice_5"] is True
    assert saved["ready_to_import"] is False
    assert saved["api_requests_sent"] == 0
    assert saved["writes_performed_to_databases"] is False
    assert "Slice 5 ready" in capsys.readouterr().out
    assert all(path.read_bytes() == raw for path, raw in inputs.items())
    with pytest.raises(SystemExit):
        script.main(args)
    original_rows = [[10, 1, 2024, 2, 3, 5.01]]
    row_digest = hashlib.sha256(
        json.dumps(original_rows[0], separators=(",", ":")).encode()
    ).digest()
    table_manifest = {
        "columns": [
            [name, "BIGINT", True]
            for name in [
                "player_id",
                "owner_id",
                "year",
                "position_id",
                "team_id",
                "amount",
            ]
        ],
        "row_count": 1,
        "all_rows_sha256": hashlib.sha256(row_digest).hexdigest(),
    }
    verification_path = tmp_path / "verification.json"
    verification_path.write_text(
        json.dumps(
            {
                "working_database": "ffpi_528_test",
                "tables": {"public.draft_picks": table_manifest},
            }
        )
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "format": "ppl-staging-events-v1",
                "database": "ffpi_528_test",
                "table": "public.draft_picks",
                "captured_at_utc": "2026-11-01T00:00:00+00:00",
                "verification_sha256": hashlib.sha256(
                    verification_path.read_bytes()
                ).hexdigest(),
                "table_manifest": table_manifest,
                "rows": original_rows,
            }
        )
    )
    args[args.index("--output") + 1] = str(tmp_path / "event-audit.json")
    args += [
        "--audit-events",
        "--staging-snapshot",
        str(snapshot_path),
        "--staging-verification",
        str(verification_path),
    ]
    assert script.main(args) == 2
    event_report = json.loads((tmp_path / "event-audit.json").read_text())
    event_audit = event_report["event_reconciliation_audit"]
    assert event_audit["ready_for_approval"] is True
    assert "Slice 6 ready" not in capsys.readouterr().out
    decisions = {
        **common,
        "teams_sha256": audit["teams_sha256"],
        "staging_snapshot_sha256": event_audit["staging_snapshot_sha256"],
        "staging_verification_sha256": event_audit["staging_verification_sha256"],
        "resolution": event_audit["proposal"],
    }
    event_path = tmp_path / "events.json"
    event_path.write_text(json.dumps(decisions))
    args += ["--event-resolutions", str(event_path)]
    args[args.index("--output") + 1] = str(tmp_path / "events-resolved.json")
    assert script.main(args) == 2
    resolved = json.loads((tmp_path / "events-resolved.json").read_text())
    assert resolved["approved_event_resolutions"]["ready_for_slice_6"] is True
    assert resolved["ready_to_import"] is False
    assert resolved["api_requests_sent"] == 0
    assert resolved["writes_performed_to_databases"] is False
    assert "Slice 6 ready" in capsys.readouterr().out
    assert all(path.read_bytes() == raw for path, raw in inputs.items())


@pytest.mark.parametrize(
    "options,message",
    [
        ({"audit_attributes": True}, "requires validated owner"),
        ({"audit_events": True}, "requires validated attribute"),
        ({"event_resolutions": {}}, "requires validated attribute"),
    ],
)
def test_later_slice_review_requires_validated_prerequisites(
    selected_exports, options, message
):
    source_root, export_root = selected_exports
    with pytest.raises(ValueError, match=message):
        script.run_source_reconciliation(
            source_root=source_root,
            season_exports={2024: export_root},
            draft_exports={},
            **options,
        )


@pytest.mark.parametrize("kind", ["player", "owner", "attribute", "event"])
@pytest.mark.parametrize("payload", [None, [], 1, "approval", True])
def test_supplied_nonobject_approval_never_skips_gate_or_claims_readiness(
    tmp_path, monkeypatch, capsys, kind, payload
):
    def unexpected(**kwargs):
        pytest.fail("Invalid approval must fail before reconciliation.")

    monkeypatch.setattr(script, "run_source_reconciliation", unexpected)
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "result.json"
    assert (
        script.main(
            [
                "--source-root",
                str(tmp_path),
                "--season-export",
                f"2024={tmp_path}",
                f"--{kind}-resolutions",
                str(path),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "ready" not in captured.out
    assert not output.exists()


def test_catalog_only_identity_can_be_resolved_without_inventing_events(
    approval_evidence,
):
    report, decisions = deepcopy(approval_evidence)
    report["seasons"][0]["player_conflict_audit"][0]["affected_draft_rows"] = []
    profile = report["player_conflict_dispositions"][0]
    profile["affected_draft_rows"] = 0
    profile["disposition"] = "blocked_catalog_only_identity_review"
    result = script.approve_player_resolutions(report, decisions)
    assert result["ready_for_slice_3"] is True
    assert result["resolved_players"][0]["legacy_event_refs"] == []
    assert result["resolved_players"][0]["catalog_evidence_refs"]


@pytest.mark.parametrize(
    "name,position,conflicting",
    [
        ("Different Player", "WR", True),
        ("AJ Brown", "RB", True),
        ("", "WR", True),
        ("AJ Brown", "WR", False),
    ],
)
def test_catalog_only_approval_checks_every_row_sharing_native_id(
    selected_exports, approval_evidence, name, position, conflicting
):
    source_root, export_root = selected_exports
    _, decisions = deepcopy(approval_evidence)
    path = source_root / "draft_results.csv"
    header = path.read_text().splitlines()[0]
    path.write_text(header + "\n", encoding="utf-8")
    path = export_root / "players" / "2024.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.append({**rows[0], "player_name": name, "position": position})
    _write_csv(path, rows)
    report = script.run_source_reconciliation(
        source_root=source_root, season_exports={2024: export_root}, draft_exports={}
    )
    decisions["legacy_source_files_sha256"] = report["legacy_source_files_sha256"]
    decisions["selected_mfl_exports"] = report["selected_mfl_exports"]
    profile = report["seasons"][0]["player_conflict_audit"][0]
    assert profile["affected_draft_rows"] == []
    conflicts = report["seasons"][0]["native_catalog_conflicts"]
    if conflicting:
        assert len(conflicts) == 1
        assert conflicts[0]["player_mfl_id"] == "123"
        assert [row["player_name"] for row in conflicts[0]["rows"]] == [
            "AJ Brown",
            name,
        ]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert {row["evidence_ref"] for row in conflicts[0]["rows"]} == {
            f"{digest}:2",
            f"{digest}:3",
        }
        with pytest.raises(ValueError, match="conflicting catalog identities"):
            script.approve_player_resolutions(report, decisions)
    else:
        assert conflicts == []
        assert script.approve_player_resolutions(report, decisions)["ready_for_slice_3"]


def test_cli_replays_approved_identity_manifest(
    approval_evidence,
    tmp_path,
    monkeypatch,
    capsys,
):
    report, decisions = approval_evidence

    def replay(**kwargs):
        return {
            **report,
            "approved_player_resolutions": script.approve_player_resolutions(
                report, kwargs["player_resolutions"]
            ),
        }

    monkeypatch.setattr(script, "run_source_reconciliation", replay)
    selection = tmp_path / "approved.json"
    selection.write_text(json.dumps(decisions), encoding="utf-8")
    output = tmp_path / "resolved.json"
    assert (
        script.main(
            [
                "--source-root",
                str(tmp_path),
                "--season-export",
                f"2024={tmp_path}",
                "--player-resolutions",
                str(selection),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["approved_player_resolutions"]["ready_for_slice_3"] is True
    assert saved["ready_to_import"] is False
    assert "Slice 3 ready" in capsys.readouterr().out


@pytest.mark.parametrize(
    "failure",
    [
        "unapproved",
        "stale_hash",
        "missing_identity",
        "duplicate_identity",
        "unreviewed_alias",
        "missing_variant",
        "wrong_native_id",
        "wrong_position",
        "uncovered_season",
        "ambiguous_event",
    ],
)
def test_approval_rejects_incomplete_stale_or_unsupported_decisions(
    approval_evidence, failure
):
    report, decisions = deepcopy(approval_evidence)
    entry = decisions["players"][0]
    if failure == "unapproved":
        decisions["approved"] = False
    elif failure == "stale_hash":
        decisions["legacy_source_files_sha256"] = {}
    elif failure == "missing_identity":
        decisions["players"] = []
    elif failure == "duplicate_identity":
        decisions["players"].append(deepcopy(entry))
    elif failure == "unreviewed_alias":
        entry["aliases_reviewed"] = False
    elif failure == "missing_variant":
        entry["reviewed_variant_sha256"].pop()
    elif failure == "wrong_native_id":
        entry["player_mfl_id"] = "999"
    elif failure == "wrong_position":
        entry["native_position"] = "DST"
    elif failure == "uncovered_season":
        report["player_conflict_dispositions"][0]["uncovered_legacy_rows"] = [99]
    elif failure == "ambiguous_event":
        report["seasons"][0]["player_conflict_audit"][0]["affected_draft_rows"][0][
            "status"
        ] = "ambiguous"
    with pytest.raises(ValueError):
        script.approve_player_resolutions(report, decisions)
