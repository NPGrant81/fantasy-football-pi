from copy import deepcopy
import hashlib
import json

import pytest

from backend.scripts import reconcile_ppl_events as script


@pytest.fixture
def event_evidence():
    players = [
        {
            "player_mfl_id": str(identifier),
            "player_name": name,
            "position": "WR",
            "nfl_team": "PHI",
            "extracted_at_utc": "2026-03-01T00:00:00Z",
        }
        for identifier, name in [
            (123, "AJ Brown"),
            (234, "Second Player"),
            (345, "Extra Player"),
        ]
    ]
    native = [
        {
            "player_mfl_id": str(identifier),
            "franchise_id": "0001",
            "winning_bid": amount,
            "raw_pick": json.dumps(
                {
                    "player": str(identifier),
                    "franchise": "0001",
                    "cost": amount,
                    "source": "auctionResults",
                    "timestamp": "1724684051",
                }
            ),
        }
        for identifier, amount in [(123, "5.01"), (234, "1"), (345, "1.00")]
    ]
    legacy = [
        {
            "PlayerID": identifier,
            "OwnerID": "1",
            "Year": "2024",
            "PositionID": "2",
            "TeamID": "3",
            "WinningBid": amount,
        }
        for identifier, amount in [("10", "5.0100"), ("20", "1")]
    ]
    events = [
        {"evidence_ref": f"native-hash:{number}", "status": "review_required"}
        for number in range(2, 5)
    ]
    return {
        "sources": {
            "draft_results.csv": legacy,
            "players.csv": [
                {"Player_ID": str(identifier), "PlayerName": name}
                for identifier, name in [
                    (10, "AJ Brown"),
                    (20, "Second Player"),
                    (30, "Extra Player"),
                ]
            ],
        },
        "report": {
            "legacy_source_files_sha256": {
                "draft_results.csv": "legacy-hash",
                "players.csv": "players-hash",
            },
            "selected_mfl_exports": [
                {"season": 2024, "report": "players", "sha256": "players-native"},
                {"season": 2024, "report": "draftResults", "sha256": "native-hash"},
            ],
            "seasons": [
                {"season": 2024, "league_mfl_id": "11422", "native_events": events}
            ],
            "approved_owner_resolutions": {
                "season_owners": [
                    {"season": 2024, "source_owner_id": 1, "franchise_id": "0001"}
                ],
                "resolved_event_owners": [
                    {
                        "legacy_evidence_ref": f"legacy-hash:{number}",
                        "native_evidence_ref": f"native-hash:{number}",
                        "resolved_source_owner_id": 1,
                    }
                    for number in range(2, 4)
                ],
            },
            "approved_player_resolutions": {"resolved_players": []},
            "approved_attribute_resolutions": {
                "teams_sha256": "teams-hash",
                "draft_rows": [
                    {
                        "legacy_evidence_ref": f"legacy-hash:{number}",
                        "position": "WR",
                        "source_team_id": 3,
                        "team_basis": "retain_legacy",
                    }
                    for number in range(2, 4)
                ],
            },
        },
        "native_seasons": {2024: {"players": players, "draftResults": native}},
        "staging": {
            "sha256": "staging-hash",
            "verification_sha256": "verification-hash",
            "database": "ffpi_528_test",
            "rows": [
                {
                    "player_id": 10,
                    "owner_id": 1,
                    "year": 2024,
                    "position_id": 2,
                    "team_id": 3,
                    "amount": 5.01,
                }
            ],
        },
    }


def _approval(evidence):
    audit = script.build_event_audit(**evidence)
    report = {**evidence["report"], "event_reconciliation_audit": audit}
    decisions = {
        "approved": True,
        "review_basis": "Explicit event and observation grain review",
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
        "teams_sha256": "teams-hash",
        "staging_snapshot_sha256": "staging-hash",
        "staging_verification_sha256": "verification-hash",
        "resolution": audit["proposal"],
    }
    return report, deepcopy(decisions)


def test_event_audit_accounts_for_gaps_supplements_and_exact_totals(event_evidence):
    before = deepcopy(event_evidence)
    report, decisions = _approval(event_evidence)
    audit = report["event_reconciliation_audit"]
    assert audit["legacy_disposition_counts"] == {
        "retain_matched_observation": 1,
        "restore_staging_gap": 1,
    }
    assert audit["native_disposition_counts"] == {
        "preserve_linked_legacy": 2,
        "supplement_native_only": 1,
    }
    assert audit["proposal"]["season_totals"] == [
        {
            "season": 2024,
            "native_rows": 3,
            "native_amount": "7.01",
            "legacy_rows": 2,
            "legacy_amount": "6.01",
            "staging_rows": 1,
            "staging_amount": "5.01",
        }
    ]
    extra = audit["proposal"]["events"][-1]
    assert extra["source_player_id"] == 30
    assert extra["source_owner_id"] == 1
    assert extra["legacy_evidence_ref"] is None
    assert (
        extra["attributes"]["team_basis"] == "season_catalog_snapshot_not_auction_time"
    )
    assert extra["source_player_candidates"][0]["legacy_catalog_refs"] == [
        "players-hash:4"
    ]
    assert audit["timestamp_observations"][2024] == {
        "distinct_values": 1,
        "shared_timestamp_additional_rows": 2,
        "establishes_chronology": False,
    }
    assert audit["ready_for_approval"] is True
    assert audit["ready_for_slice_6"] is False
    resolved = script.approve_event_resolutions(report, decisions)
    assert resolved["ready_for_slice_6"] is True
    assert resolved["ready_to_import"] is False
    assert resolved["writes_performed_to_databases"] is False
    assert event_evidence == before


def test_observation_keys_ignore_formatting_and_preserve_decimal_precision():
    args = {
        "league_mfl_id": "11422",
        "season": 2024,
        "player_mfl_id": "00123",
        "franchise_id": "0001",
    }
    key = script.auction_observation_key(**args, winning_bid="5.010000")
    assert key == script.auction_observation_key(**args, winning_bid="$5.01")
    assert key != script.auction_observation_key(
        **args, winning_bid="5.010000000000000000000000000001"
    )
    for column, value in [
        ("season", 2025),
        ("player_mfl_id", "123"),
        ("franchise_id", "0002"),
        ("league_mfl_id", "38909"),
    ]:
        assert key != script.auction_observation_key(
            **{**args, column: value}, winning_bid="5.01"
        )


def test_reordered_exports_and_changed_extraction_times_do_not_change_keys(
    event_evidence,
):
    before = script.build_event_audit(**event_evidence)
    exports = event_evidence["native_seasons"][2024]
    exports["draftResults"].reverse()
    for row in exports["draftResults"]:
        row["extracted_at_utc"] = "2030-01-01"
    report = event_evidence["report"]
    for selected in report["selected_mfl_exports"]:
        if selected["report"] == "draftResults":
            selected["sha256"] = "reordered-native"
    report["seasons"][0]["native_events"] = [
        {"evidence_ref": f"reordered-native:{number}", "status": "review_required"}
        for number in range(2, 5)
    ]
    for row in report["approved_owner_resolutions"]["resolved_event_owners"]:
        old_number = int(row["native_evidence_ref"].split(":")[-1])
        row["native_evidence_ref"] = f"reordered-native:{6 - old_number}"
    after = script.build_event_audit(**event_evidence)
    assert sorted(
        e["source_event_key"] for e in before["proposal"]["events"]
    ) == sorted(e["source_event_key"] for e in after["proposal"]["events"])


def test_identical_native_rows_are_retained_and_blocked_not_deduplicated(
    event_evidence,
):
    exports = event_evidence["native_seasons"][2024]
    exports["draftResults"].append(deepcopy(exports["draftResults"][-1]))
    event_evidence["report"]["seasons"][0]["native_events"].append(
        {"evidence_ref": "native-hash:5", "status": "review_required"}
    )
    report, decisions = _approval(event_evidence)
    audit = report["event_reconciliation_audit"]
    assert len(audit["proposal"]["events"]) == 4
    assert any(
        b["kind"] == "identical_observation_collisions" for b in audit["blockers"]
    )
    assert audit["proposal"]["repeated_player_observations"][0][
        "native_evidence_refs"
    ] == ["native-hash:4", "native-hash:5"]
    with pytest.raises(ValueError, match="Unresolved event"):
        script.approve_event_resolutions(report, decisions)


def test_event_totals_do_not_round_beyond_decimal_default_precision(event_evidence):
    row = event_evidence["native_seasons"][2024]["draftResults"][-1]
    row["winning_bid"] = "1.000000000000000000000000000001"
    raw = json.loads(row["raw_pick"])
    raw["cost"] = row["winning_bid"]
    row["raw_pick"] = json.dumps(raw)
    audit = script.build_event_audit(**event_evidence)
    assert audit["proposal"]["season_totals"][0]["native_amount"] == (
        "7.010000000000000000000000000001"
    )


def test_distinct_repeated_acquisition_observations_survive_without_chronology(
    event_evidence,
):
    exports = event_evidence["native_seasons"][2024]
    extra = deepcopy(exports["draftResults"][-1])
    extra["winning_bid"] = "2"
    raw = json.loads(extra["raw_pick"])
    raw["cost"] = "2"
    extra["raw_pick"] = json.dumps(raw)
    exports["draftResults"].append(extra)
    event_evidence["report"]["seasons"][0]["native_events"].append(
        {"evidence_ref": "native-hash:5", "status": "review_required"}
    )
    audit = script.build_event_audit(**event_evidence)
    assert audit["ready_for_approval"]
    assert len(audit["proposal"]["events"]) == 4
    assert len({e["source_event_key"] for e in audit["proposal"]["events"]}) == 4
    assert len(audit["proposal"]["repeated_player_observations"]) == 1
    assert audit["timestamp_observations"][2024]["establishes_chronology"] is False


def test_cross_season_player_observations_are_never_collapsed(event_evidence):
    event_evidence["native_seasons"][2025] = deepcopy(
        event_evidence["native_seasons"][2024]
    )
    event_evidence["report"]["selected_mfl_exports"] += [
        {"season": 2025, "report": "players", "sha256": "players-2025"},
        {"season": 2025, "report": "draftResults", "sha256": "native-2025"},
    ]
    season = deepcopy(event_evidence["report"]["seasons"][0])
    season["season"] = 2025
    for event in season["native_events"]:
        event["evidence_ref"] = event["evidence_ref"].replace(
            "native-hash", "native-2025"
        )
    event_evidence["report"]["seasons"].append(season)
    event_evidence["report"]["approved_owner_resolutions"]["season_owners"].append(
        {"season": 2025, "source_owner_id": 1, "franchise_id": "0001"}
    )
    audit = script.build_event_audit(**event_evidence)
    assert audit["ready_for_approval"]
    assert len({e["source_event_key"] for e in audit["proposal"]["events"]}) == 6
    assert len(audit["proposal"]["players_in_multiple_seasons"]) == 3


def test_empty_selected_season_cannot_be_certified_as_complete(event_evidence):
    event_evidence["native_seasons"][2025] = {"players": [], "draftResults": []}
    event_evidence["report"]["seasons"].append(
        {"season": 2025, "league_mfl_id": "11422", "native_events": []}
    )
    report, decisions = _approval(event_evidence)
    assert {"kind": "empty_native_season_requires_review", "season": 2025} in (
        report["event_reconciliation_audit"]["blockers"]
    )
    with pytest.raises(ValueError, match="Unresolved event"):
        script.approve_event_resolutions(report, decisions)


def test_staging_multiset_keeps_duplicate_occurrences_and_blocks_unexpected_rows(
    event_evidence,
):
    rows = event_evidence["staging"]["rows"]
    rows.append(deepcopy(rows[0]))
    report, decisions = _approval(event_evidence)
    audit = report["event_reconciliation_audit"]
    assert audit["unexpected_staging_refs"] == ["staging-hash:2"]
    with pytest.raises(ValueError, match="Unresolved event"):
        script.approve_event_resolutions(report, decisions)


@pytest.mark.parametrize(
    "column,value", [("position_id", 9), ("team_id", 4), ("amount", 5.0101)]
)
def test_staging_comparison_uses_original_attributes_and_exact_bid(
    event_evidence, column, value
):
    event_evidence["staging"]["rows"][0][column] = value
    audit = script.build_event_audit(**event_evidence)
    assert audit["legacy_disposition_counts"] == {"restore_staging_gap": 2}
    assert audit["unexpected_staging_refs"] == ["staging-hash:1"]


@pytest.mark.parametrize(
    "problem",
    ["ambiguous_player", "missing_owner", "raw_disagreement", "catalog_disagreement"],
)
def test_unresolved_supplement_never_passes_gate(event_evidence, problem):
    exports = event_evidence["native_seasons"][2024]
    if problem == "ambiguous_player":
        event_evidence["sources"]["players.csv"].append(
            {"Player_ID": "40", "PlayerName": "Extra Player"}
        )
    elif problem == "missing_owner":
        event_evidence["report"]["approved_owner_resolutions"]["season_owners"] = []
    elif problem == "raw_disagreement":
        raw = json.loads(exports["draftResults"][-1]["raw_pick"])
        raw["cost"] = "999"
        exports["draftResults"][-1]["raw_pick"] = json.dumps(raw)
    else:
        exports["players"].append({**exports["players"][-1], "position": "RB"})
    report, decisions = _approval(event_evidence)
    assert report["event_reconciliation_audit"]["blockers"]
    with pytest.raises(ValueError, match="Unresolved event"):
        script.approve_event_resolutions(report, decisions)


@pytest.mark.parametrize(
    "problem",
    [
        "unapproved",
        "basis",
        "legacy",
        "exports",
        "teams",
        "snapshot",
        "verification",
        "gap",
        "event",
        "grain",
        "totals",
    ],
)
def test_event_approval_requires_all_evidence_dispositions_and_grain(
    event_evidence, problem
):
    report, decisions = _approval(event_evidence)
    if problem == "unapproved":
        decisions["approved"] = False
    elif problem == "basis":
        decisions["review_basis"] = ""
    elif problem in {"legacy", "exports", "teams", "snapshot", "verification"}:
        key = {
            "legacy": "legacy_source_files_sha256",
            "exports": "selected_mfl_exports",
            "teams": "teams_sha256",
            "snapshot": "staging_snapshot_sha256",
            "verification": "staging_verification_sha256",
        }[problem]
        decisions[key] = "stale"
    elif problem == "gap":
        decisions["resolution"]["legacy_coverage"] = []
    elif problem == "event":
        decisions["resolution"]["events"] = decisions["resolution"]["events"][:-1]
    elif problem == "grain":
        decisions["resolution"]["event_grain"]["identical_key_policy"] = "deduplicate"
    else:
        decisions["resolution"]["season_totals"][0]["native_amount"] = "7.02"
    with pytest.raises(ValueError):
        script.approve_event_resolutions(report, decisions)


@pytest.fixture
def staging_files(tmp_path):
    rows = [[10, 1, 2024, 2, 3, 5.01]]
    manifest = {
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
        "all_rows_sha256": hashlib.sha256(
            b"".join(sorted(bytes.fromhex(script._digest(row)) for row in rows))
        ).hexdigest(),
    }
    baseline = tmp_path / "verification.json"
    baseline.write_text(
        json.dumps(
            {
                "working_database": "ffpi_528_test",
                "tables": {"public.draft_picks": manifest},
            }
        )
    )
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "format": "ppl-staging-events-v1",
                "database": "ffpi_528_test",
                "table": "public.draft_picks",
                "captured_at_utc": "2026-11-01T00:00:00+00:00",
                "verification_sha256": hashlib.sha256(
                    baseline.read_bytes()
                ).hexdigest(),
                "table_manifest": manifest,
                "rows": rows,
            }
        )
    )
    return snapshot, baseline


def test_staging_snapshot_verifies_complete_preserved_row_hash(staging_files):
    snapshot, baseline = staging_files
    result = script.read_staging_snapshot(snapshot, baseline)
    assert result["rows"][0]["amount"] == 5.01
    assert result["sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "problem",
    ["null", "database", "verification", "rows", "columns", "capture", "count"],
)
def test_tampered_staging_snapshots_are_rejected(staging_files, problem):
    snapshot, baseline = staging_files
    value = json.loads(snapshot.read_text())
    if problem == "null":
        value = None
    elif problem == "database":
        value["database"] = "fantasy_football_etl"
    elif problem == "verification":
        value["verification_sha256"] = "stale"
    elif problem == "rows":
        value["rows"][0][-1] = 5.02
    elif problem == "columns":
        value["table_manifest"]["columns"][0][0] = "other"
    elif problem == "capture":
        value["captured_at_utc"] = "2026-11-01"
    else:
        value["rows"] = []
    snapshot.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        script.read_staging_snapshot(snapshot, baseline)
