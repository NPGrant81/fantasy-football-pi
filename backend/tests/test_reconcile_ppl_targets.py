from copy import deepcopy

import pytest
import sqlalchemy as sa

from backend.scripts import reconcile_ppl_targets as script
from backend.scripts.reconcile_ppl_events import auction_observation_key


@pytest.fixture
def target_evidence():
    event = {
        "season": 2024,
        "league_mfl_id": "11422",
        "player_mfl_id": "00123",
        "franchise_id": "0001",
        "winning_bid": "5.01",
    }
    event["source_event_key"] = auction_observation_key(**event)
    return {
        "report": {
            "approved_event_resolutions": {
                "ready_for_slice_6": True,
                "resolution": {"events": [event]},
            },
            "selected_mfl_exports": [
                {"season": 2024, "report": "players", "sha256": "native-hash"}
            ],
        },
        "native_seasons": {
            2024: {
                "players": [
                    {
                        "player_mfl_id": "00123",
                        "player_name": "Brown, A.J.",
                        "position": "WR",
                    }
                ]
            }
        },
        "snapshot": {
            "database": "ffpi_528_slice6_test",
            "league": {"id": 60},
            "revision": script.TARGET_REVISION,
            "schema_sha256": script.REVIEWED_SCHEMA_DIGEST,
            "table_digests": {"players": (3, "snapshot-hash")},
            "players": [
                {
                    "id": identifier,
                    "name": "AJ Brown Jr.",
                    "position": "WR",
                    "nfl_team": team,
                    "mfl_id": None,
                    "gsis_id": None,
                    "espn_id": None,
                    "sleeper_id": None,
                }
                for identifier, team in [(10, "TEN"), (20, "PHI"), (30, "PHI")]
            ],
            "player_seasons": [
                {
                    "id": identifier,
                    "player_id": player,
                    "season": 2024,
                    "mfl_id": "00123",
                    "position": "WR",
                    "source": "mfl",
                }
                for identifier, player in [(1, 10), (2, 20)]
            ],
            "users": [],
            "league_mfl_seasons": [
                {"league_id": 60, "season": 2024, "mfl_league_id": "11422"}
            ],
        },
    }


def test_target_proposals_preserve_evidence_without_approval_or_writes(target_evidence):
    before = deepcopy(target_evidence)
    report = script.build_target_review(**target_evidence)
    player = report["players"][0]
    assert player["player_mfl_id"] == "00123"
    assert player["name_only_candidate_ids"] == [30]
    assert player["proposed_target_player_id"] == 10
    assert [
        row["target_player_id"] for row in player["native_corroborated_candidates"]
    ] == [10, 20]
    assert player["native_corroborated_candidates"][0]["same_season_evidence"] == [
        {
            "player_season_id": 1,
            "season": 2024,
            "native_catalog_refs": ["native-hash:2"],
        }
    ]
    assert report["summary"] == {
        "events": 1,
        "exact_bid_total": "5.01",
        "players": 1,
        "native_candidate_counts": {2: 1},
        "archival_account_dispositions": {"create_nonlogin_archival": 1},
    }
    assert report["ready_for_mapping_review"] is True
    assert report["approved"] is report["ready_to_import"] is False
    assert report["writes_performed_to_databases"] is False
    assert report["season_franchises"][0]["approved"] is False
    assert "AJ Brown" not in str(report)
    assert target_evidence == before


def test_existing_corroborated_native_binding_takes_precedence(target_evidence):
    target_evidence["snapshot"]["players"][1]["mfl_id"] = "00123"
    report = script.build_target_review(**target_evidence)
    assert report["players"][0]["proposed_target_player_id"] == 20


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("label", "same_season_identity_disagreement"),
        ("native", "conflicting_canonical_native_id"),
        ("source", "unverified_season_provider"),
        ("dangling", "dangling_target_player"),
        ("season_position", "same_season_identity_disagreement"),
        ("cross_native", "target_linked_to_multiple_native_ids"),
    ],
)
def test_contradictory_evidence_blocks_representative_selection(
    target_evidence, mutation, reason
):
    snapshot = target_evidence["snapshot"]
    if mutation == "label":
        snapshot["players"][0]["name"] = "Different Player"
    elif mutation == "native":
        snapshot["players"][0]["mfl_id"] = "00456"
    elif mutation == "source":
        snapshot["player_seasons"][0]["source"] = "unknown"
    elif mutation == "dangling":
        snapshot["player_seasons"][0]["player_id"] = 999
    elif mutation == "season_position":
        snapshot["player_seasons"][0]["position"] = "RB"
    else:
        snapshot["player_seasons"].append(
            {
                **snapshot["player_seasons"][0],
                "id": 3,
                "mfl_id": "00456",
                "season": 2001,
            }
        )
    report = script.build_target_review(**target_evidence)
    assert report["players"][0]["rejected_season_links"][0]["reason"] == reason
    assert report["players"][0]["proposed_target_player_id"] == 20
    assert report["ready_for_mapping_review"] is False


def test_name_only_and_unselected_season_evidence_never_approve_identity(
    target_evidence,
):
    for row in target_evidence["snapshot"]["player_seasons"]:
        row["season"] = 2001
    report = script.build_target_review(**target_evidence)
    assert report["players"][0]["name_only_candidate_ids"] == [10, 20, 30]
    assert report["players"][0]["proposed_target_player_id"] is None
    assert report["ready_for_mapping_review"] is False


def test_competing_provider_ids_across_native_candidates_block_review(target_evidence):
    target_evidence["snapshot"]["players"][0]["gsis_id"] = "one"
    target_evidence["snapshot"]["players"][1]["gsis_id"] = "two"
    report = script.build_target_review(**target_evidence)
    assert report["players"][0]["proposed_target_player_id"] is None
    assert (
        "conflicting_provider_ids_across_candidates" in report["blockers"][0]["reasons"]
    )


def _archival_user():
    return {
        "id": 50,
        "username": "hist_2024_0001",
        "league_id": 60,
        "is_historical_stub": True,
        "is_superuser": False,
        "is_commissioner": False,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"league_id": 61},
        {"is_historical_stub": False},
        {"is_superuser": True},
        {"is_commissioner": True},
        {"username": "HIST_2024_0001"},
    ],
)
def test_existing_live_or_foreign_account_is_not_repurposed(target_evidence, changes):
    target_evidence["snapshot"]["users"] = [{**_archival_user(), **changes}]
    report = script.build_target_review(**target_evidence)
    assert report["ready_for_mapping_review"] is False
    assert report["blockers"][0]["kind"] == "unsafe_archival_account_collision"
    assert report["season_franchises"][0]["target_owner_id"] is None


def test_exact_nonprivileged_same_league_archival_account_can_be_proposed(
    target_evidence,
):
    target_evidence["snapshot"]["users"] = [_archival_user()]
    report = script.build_target_review(**target_evidence)
    owner = report["season_franchises"][0]
    assert owner["target_owner_id"] == 50
    assert owner["disposition"] == "reuse_archival"
    assert owner["approved"] is False


@pytest.mark.parametrize(
    "changes", [[], [{"league_id": 60, "season": 2024, "mfl_league_id": "99999"}]]
)
def test_missing_or_different_native_league_mapping_blocks(target_evidence, changes):
    target_evidence["snapshot"]["league_mfl_seasons"] = changes
    assert (
        script.build_target_review(**target_evidence)["ready_for_mapping_review"]
        is False
    )


def test_snapshot_or_source_change_invalidates_review_binding(target_evidence):
    original = script.build_target_review(**target_evidence)
    target_evidence["snapshot"]["table_digests"]["players"] = (4, "changed")
    changed = script.build_target_review(**target_evidence)
    assert original["target_snapshot_sha256"] != changed["target_snapshot_sha256"]
    target_evidence["report"]["approved_event_resolutions"][
        "review_basis"
    ] = "new review"
    changed_again = script.build_target_review(**target_evidence)
    assert (
        changed["source_event_approval_sha256"]
        != changed_again["source_event_approval_sha256"]
    )


@pytest.mark.parametrize(
    "mutation", ["unapproved", "changed_event", "duplicate", "empty"]
)
def test_source_event_approval_is_required_and_event_keys_are_rechecked(
    target_evidence, mutation
):
    approval = target_evidence["report"]["approved_event_resolutions"]
    if mutation == "unapproved":
        approval["ready_for_slice_6"] = False
    elif mutation == "changed_event":
        approval["resolution"]["events"][0]["winning_bid"] = "6"
    elif mutation == "duplicate":
        approval["resolution"]["events"] *= 2
    else:
        approval["resolution"]["events"] = []
    with pytest.raises(ValueError):
        script.build_target_review(**target_evidence)


@pytest.mark.parametrize(
    "url,name",
    [
        ("sqlite://", "ffpi_528_slice6_test"),
        ("postgresql://localhost/fantasy_football", "fantasy_football"),
        ("postgresql://remote/ffpi_528_slice6_test", "ffpi_528_slice6_test"),
        ("postgresql://localhost/ffpi_528_slice6_other", "ffpi_528_slice6_test"),
        (
            "postgresql://localhost/ffpi_528_slice6_test?dbname=other",
            "ffpi_528_slice6_test",
        ),
        (
            "postgresql://localhost/ffpi_528_slice6_test?options=x",
            "ffpi_528_slice6_test",
        ),
        (
            "postgresql://localhost/ffpi_528_slice6_test?host=remote",
            "ffpi_528_slice6_test",
        ),
        (
            "postgresql://localhost/ffpi_528_slice6_test?hostaddr=192.0.2.1",
            "ffpi_528_slice6_test",
        ),
    ],
)
def test_connection_guard_rejects_unsafe_targets_before_connecting(url, name):
    engine = sa.create_engine(url)
    try:
        with pytest.raises(ValueError, match="explicit loopback"):
            script.capture_target_snapshot(engine, name, 60)
    finally:
        engine.dispose()


def _target_approval(evidence):
    report = deepcopy(evidence["report"])
    report["target_mapping_review"] = script.build_target_review(**evidence)
    decisions = {
        "approved": True,
        "review_basis": "Explicit representative and archival-account review",
        "review_sha256": script._digest(report),
        "resolution": script.target_resolution_proposal(
            report["target_mapping_review"]
        ),
    }
    return report, decisions


def test_target_approval_is_hash_bound_and_does_not_authorize_production(
    target_evidence,
):
    report, decisions = _target_approval(target_evidence)
    approved = script.approve_target_resolutions(report, decisions)
    assert approved["approved"] is True
    assert approved["scope"] == "new_local_working_clone_only_not_production"
    assert approved["resolution"]["players"] == [
        {"player_mfl_id": "00123", "target_player_id": 10}
    ]


@pytest.mark.parametrize(
    "mutation", ["hash", "approval", "target", "account", "source"]
)
def test_target_approval_rejects_changed_or_partial_resolutions(
    target_evidence, mutation
):
    report, decisions = _target_approval(target_evidence)
    if mutation == "hash":
        decisions["review_sha256"] = "changed"
    elif mutation == "approval":
        decisions["approved"] = False
    elif mutation == "target":
        decisions["resolution"]["players"][0]["target_player_id"] = 20
    elif mutation == "account":
        decisions["resolution"]["season_franchises"] = []
    else:
        report["approved_event_resolutions"]["review_basis"] = "changed"
    with pytest.raises(ValueError):
        script.approve_target_resolutions(report, decisions)


def test_mixed_native_links_must_be_explicitly_excluded_and_preserved(target_evidence):
    snapshot = target_evidence["snapshot"]
    snapshot["player_seasons"].append(
        {**snapshot["player_seasons"][0], "id": 3, "season": 2001, "mfl_id": "00999"}
    )
    report, decisions = _target_approval(target_evidence)
    assert decisions["resolution"]["players"][0]["target_player_id"] == 20
    assert len(decisions["resolution"]["excluded_season_links"]) == 1
    assert script.approve_target_resolutions(report, decisions)["approved"] is True
    decisions["resolution"]["excluded_season_links"] = []
    with pytest.raises(ValueError):
        script.approve_target_resolutions(report, decisions)
