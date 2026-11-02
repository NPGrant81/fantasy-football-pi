from copy import deepcopy
import hashlib

import pytest

from backend.scripts import reconcile_ppl_attributes as script


@pytest.fixture
def attribute_evidence(tmp_path):
    teams = tmp_path / "teams.csv"
    teams.write_text("Team,TeamID\nPHI,3\nFA,4\nFA*,4\n", encoding="ascii")
    return {
        "teams_path": teams,
        "sources": {
            "positions.csv": [
                {"PositionID": "2", "Position": "WR"},
                {"PositionID": "6", "Position": "Def"},
                {"PositionID": "6", "Position": "TD"},
                {"PositionID": "9", "Position": "Kicker"},
                {"PositionID": "9", "Position": "PK"},
            ],
            "players.csv": [
                {"Player_ID": "10", "PlayerName": "Test Player", "PositionID": "2"},
                {"Player_ID": "11", "PlayerName": "Unlinked", "PositionID": "2"},
            ],
            "draft_results.csv": [
                {"PlayerID": "10", "Year": "2024", "PositionID": "2", "TeamID": "3"}
            ],
        },
        "native_seasons": {
            2024: {
                "players": [
                    {
                        "player_mfl_id": "0123",
                        "position": "WR",
                        "nfl_team": "PHI",
                        "extracted_at_utc": "2026-03-01T00:00:00Z",
                    }
                ]
            }
        },
        "report": {
            "legacy_source_files_sha256": {
                "positions.csv": "positions-hash",
                "players.csv": "players-hash",
                "draft_results.csv": "draft-hash",
            },
            "selected_mfl_exports": [
                {"season": 2024, "report": "players", "sha256": "native-players"}
            ],
            "seasons": [
                {
                    "season": 2024,
                    "native_events": [
                        {"evidence_ref": "native-event:2", "player_mfl_id": "0123"}
                    ],
                }
            ],
            "approved_owner_resolutions": {
                "resolved_event_owners": [
                    {
                        "legacy_evidence_ref": "draft-hash:2",
                        "native_evidence_ref": "native-event:2",
                    }
                ]
            },
            "approved_player_resolutions": {"resolved_players": []},
        },
    }


def _approval(evidence):
    audit = script.build_attribute_audit(**evidence)
    report = {**evidence["report"], "attribute_repair_audit": audit}
    decisions = {
        "approved": True,
        "review_basis": "Explicit row-specific snapshot attribution review",
        "legacy_source_files_sha256": report["legacy_source_files_sha256"],
        "selected_mfl_exports": report["selected_mfl_exports"],
        "teams_sha256": audit["teams_sha256"],
        "taxonomy": audit["taxonomy_proposals"],
        "draft_rows": [row["proposal"] for row in audit["draft_rows"]],
        "catalog_positions": [
            row["proposal"] for row in audit["catalog_rows"] if row["proposal"]
        ],
    }
    return report, deepcopy(decisions)


def test_attribute_audit_preserves_sources_and_requires_explicit_review(
    attribute_evidence,
):
    before = deepcopy(attribute_evidence)
    report, decisions = _approval(attribute_evidence)
    audit = report["attribute_repair_audit"]
    assert (
        audit["teams_sha256"]
        == hashlib.sha256(attribute_evidence["teams_path"].read_bytes()).hexdigest()
    )
    assert audit["taxonomy_proposals"][1]["position"] == "DST"
    assert audit["taxonomy_proposals"][2]["position"] == "DST"
    assert audit["taxonomy_proposals"][3]["position"] == "K"
    assert audit["ready_for_approval"] is True
    assert audit["ready_for_slice_5"] is False
    assert audit["catalog_rows"][1]["status"] == "outside_reviewed_identity_scope"
    row = audit["draft_rows"][0]
    assert row["proposal"]["player_mfl_id"] == "0123"
    assert row["native_catalog_observations"][0]["extracted_at_utc"]
    resolved = script.approve_attribute_resolutions(report, decisions)
    assert resolved["ready_for_slice_5"] is True
    assert resolved["ready_to_import"] is False
    assert resolved["writes_performed_to_databases"] is False
    assert attribute_evidence == before


@pytest.mark.parametrize("position,team", [("", ""), ("#N/A", "#N/A"), ("9", "99")])
def test_missing_invalid_and_reused_attributes_are_row_specific(
    attribute_evidence, position, team
):
    original = attribute_evidence["sources"]["draft_results.csv"][0]
    original.update(PositionID=position, TeamID=team)
    audit = script.build_attribute_audit(**attribute_evidence)
    row = audit["draft_rows"][0]
    assert row["original_position_id"] == position
    assert row["original_team_id"] == team
    assert row["proposal"]["position"] == "WR"
    assert row["proposal"]["source_team_id"] == 3
    assert row["team_basis"] == "season_catalog_snapshot_not_auction_time"
    assert audit["ready_for_approval"] is True


def test_valid_but_differing_team_is_an_explicit_snapshot_proposal(attribute_evidence):
    attribute_evidence["sources"]["draft_results.csv"][0]["TeamID"] = "4"
    audit = script.build_attribute_audit(**attribute_evidence)
    row = audit["draft_rows"][0]
    assert row["original_team_id"] == "4"
    assert row["team_catalog_differs"] is True
    assert row["legacy_team_labels"] == ["FA", "FA*"]
    assert row["proposal"]["source_team_id"] == 3
    assert row["approved"] is False


def test_shared_team_aliases_do_not_create_false_repairs(attribute_evidence):
    attribute_evidence["sources"]["draft_results.csv"][0]["TeamID"] = "4"
    attribute_evidence["native_seasons"][2024]["players"][0]["nfl_team"] = "FA*"
    row = script.build_attribute_audit(**attribute_evidence)["draft_rows"][0]
    assert row["proposal"]["source_team_id"] == 4
    assert row["team_basis"] == "retain_legacy"


@pytest.mark.parametrize("problem", ["blank_team", "conflict", "bad_position"])
def test_unsupported_catalog_attributes_block_approval(attribute_evidence, problem):
    players = attribute_evidence["native_seasons"][2024]["players"]
    if problem == "conflict":
        players.append({**players[0], "nfl_team": "FA"})
    elif problem == "blank_team":
        players[0]["nfl_team"] = ""
    else:
        players[0]["position"] = "TMWR"
    report, decisions = _approval(attribute_evidence)
    assert report["attribute_repair_audit"]["ready_for_approval"] is False
    with pytest.raises(ValueError, match="Unresolved attribute"):
        script.approve_attribute_resolutions(report, decisions)


def test_shortened_optional_team_cell_is_saved_as_an_explicit_blocker(
    attribute_evidence, tmp_path
):
    from backend.scripts.reconcile_ppl_mfl_sources import _read_export

    path = tmp_path / "players.csv"
    path.write_text(
        "season,league_id,source_system,source_endpoint,extracted_at_utc,"
        "player_mfl_id,player_name,position,nfl_team\n"
        "2024,11422,mfl,players,2026-03-01T00:00:00Z,0123,Test Player,WR\n",
        encoding="utf-8",
    )
    rows, digest = _read_export(path, "players", 2024)
    assert rows[0]["nfl_team"] is None
    attribute_evidence["native_seasons"][2024]["players"] = rows
    attribute_evidence["report"]["selected_mfl_exports"][0]["sha256"] = digest
    report, decisions = _approval(attribute_evidence)
    audit = report["attribute_repair_audit"]
    assert audit["draft_rows"][0]["status"] == "blocked"
    assert audit["draft_rows"][0]["native_catalog_observations"][0]["nfl_team"] == ""
    with pytest.raises(ValueError, match="Unresolved attribute"):
        script.approve_attribute_resolutions(report, decisions)


def test_catalog_position_changes_remain_season_specific(attribute_evidence):
    row = attribute_evidence["native_seasons"][2024]["players"][0]
    row["position"] = "TE"
    attribute_evidence["native_seasons"][2021] = {
        "players": [{**row, "position": "QB"}]
    }
    attribute_evidence["report"]["selected_mfl_exports"].append(
        {"season": 2021, "report": "players", "sha256": "2021-native"}
    )
    attribute_evidence["report"]["approved_player_resolutions"]["resolved_players"] = [
        {"source_player_id": 10, "player_mfl_id": "0123"}
    ]
    audit = script.build_attribute_audit(**attribute_evidence)
    row = audit["catalog_rows"][0]
    assert row["status"] == "season_specific_positions"
    assert row["proposal"]["season_positions"] == [
        {"season": 2021, "position": "QB"},
        {"season": 2024, "position": "TE"},
    ]
    assert audit["ready_for_approval"] is True


@pytest.mark.parametrize(
    "problem",
    [
        "unapproved",
        "basis",
        "legacy_hash",
        "export_hash",
        "teams_hash",
        "missing_row",
        "duplicate_row",
        "native_event",
        "team_basis",
        "taxonomy",
        "catalog",
    ],
)
def test_stale_incomplete_or_altered_attribute_approval_is_rejected(
    attribute_evidence, problem
):
    report, decisions = _approval(attribute_evidence)
    if problem == "unapproved":
        decisions["approved"] = False
    elif problem == "basis":
        decisions["review_basis"] = ""
    elif problem == "legacy_hash":
        decisions["legacy_source_files_sha256"] = {}
    elif problem == "export_hash":
        decisions["selected_mfl_exports"] = []
    elif problem == "teams_hash":
        decisions["teams_sha256"] = "stale"
    elif problem == "missing_row":
        decisions["draft_rows"] = []
    elif problem == "duplicate_row":
        decisions["draft_rows"] *= 2
    elif problem == "native_event":
        decisions["draft_rows"][0]["native_evidence_ref"] = "other"
    elif problem == "team_basis":
        decisions["draft_rows"][0]["team_basis"] = "auction_time"
    elif problem == "taxonomy":
        decisions["taxonomy"][1]["position"] = "K"
    else:
        decisions["catalog_positions"] = []
    with pytest.raises(ValueError):
        script.approve_attribute_resolutions(report, decisions)


@pytest.mark.parametrize(
    "content",
    ["Other,TeamID\nPHI,3\n", "Team,TeamID\n,3\n", "Team,TeamID\nPHI,3\nPHI,4\n"],
)
def test_invalid_team_taxonomy_fails_explicitly(attribute_evidence, content):
    attribute_evidence["teams_path"].write_text(content, encoding="ascii")
    with pytest.raises(ValueError, match="taxonomy"):
        script.build_attribute_audit(**attribute_evidence)
