import pandas as pd

from etl.transform.historical_draft_validator import validate_historical_draft_results
from etl.transform.owner_budget_timeline import build_owner_budget_timeline
from etl.transform.player_metadata_canonicalization import canonicalize_player_metadata


def test_player_metadata_canonicalization_is_deterministic_and_normalized():
    players = pd.DataFrame(
        [
            {"Player_ID": 1, "PlayerName": "CeeDee Lamb", "PositionID": 4},
            {"Player_ID": 1, "PlayerName": "Cee Dee Lamb", "PositionID": 4},
            {"Player_ID": 2, "PlayerName": "Cowboys DST", "PositionID": 99},
        ]
    )
    positions = pd.DataFrame(
        [
            {"PositionID": 4, "Position": "WR"},
            {"PositionID": 99, "Position": "D/ST"},
        ]
    )
    aliases = {"Cee Dee Lamb": "CeeDee Lamb"}

    first_canonical, first_report = canonicalize_player_metadata(players, positions, alias_map=aliases)
    second_canonical, second_report = canonicalize_player_metadata(
        players.sample(frac=1.0, random_state=7),
        positions,
        alias_map=aliases,
    )

    assert len(first_canonical) == 2
    assert first_report["content_digest"] == second_report["content_digest"]
    assert set(first_canonical["canonical_position"].tolist()) == {"WR", "DEF"}


def test_owner_budget_timeline_builds_cumulative_spend_and_reconciliation():
    draft_budget = pd.DataFrame(
        [
            {"OwnerID": 10, "Year": 2026, "DraftBudget": 200},
            {"OwnerID": 11, "Year": 2026, "DraftBudget": 200},
        ]
    )
    draft_results = pd.DataFrame(
        [
            {"PlayerID": 1001, "OwnerID": 10, "Year": 2026, "WinningBid": 20},
            {"PlayerID": 1002, "OwnerID": 10, "Year": 2026, "WinningBid": 10},
            {"PlayerID": 1003, "OwnerID": 11, "Year": 2026, "WinningBid": 15},
        ]
    )
    users = pd.DataFrame(
        [
            {"OwnerID": 10, "OwnerName": "Owner 10"},
            {"OwnerID": 11, "OwnerName": "Owner 11"},
        ]
    )

    timeline, report = build_owner_budget_timeline(draft_budget, draft_results, users)

    assert len(timeline) == 3
    owner_10_rows = timeline[timeline["owner_id"] == 10].sort_values("event_sequence")
    assert owner_10_rows.iloc[0]["remaining_budget"] == 180.0
    assert owner_10_rows.iloc[1]["remaining_budget"] == 170.0
    assert report["timeline_rows"] == 3
    assert len(report["exceptions"]) == 0


def test_historical_draft_validator_flags_duplicates_and_missing_refs():
    draft = pd.DataFrame(
        [
            {"PlayerID": 100, "OwnerID": 10, "Year": 2025, "PositionID": 4, "TeamID": 1, "WinningBid": 10},
            {"PlayerID": 100, "OwnerID": 10, "Year": 2025, "PositionID": 4, "TeamID": 1, "WinningBid": 9},
            {"PlayerID": -1, "OwnerID": -1, "Year": 2025, "PositionID": -1, "TeamID": 1, "WinningBid": 5},
        ]
    )
    players = pd.DataFrame([{"Player_ID": 100}])
    users = pd.DataFrame([{"OwnerID": 10, "OwnerName": "Owner 10"}])
    positions = pd.DataFrame([{"PositionID": 4, "Position": "WR"}])

    validated_df, correction_df, report = validate_historical_draft_results(
        draft,
        players_df=players,
        users_df=users,
        positions_df=positions,
    )

    assert report["duplicate_key_count"] == 1
    assert report["error_count"] >= 3
    assert not correction_df.empty
    assert len(validated_df) == 1


# ---------------------------------------------------------------------------
# Issue #105 – enhancements: position resolution, keeper labeling, year
# completeness, richer correction ledger
# ---------------------------------------------------------------------------

def _base_draft():
    """Minimal valid 3-pick draft fixture (2021, all valid references)."""
    return pd.DataFrame([
        {"PlayerID": 1, "OwnerID": 10, "Year": 2021, "PositionID": 4, "TeamID": 1, "WinningBid": "$50.00"},
        {"PlayerID": 2, "OwnerID": 10, "Year": 2021, "PositionID": 4, "TeamID": 1, "WinningBid": "$1.00"},
        {"PlayerID": 3, "OwnerID": 10, "Year": 2021, "PositionID": 4, "TeamID": 1, "WinningBid": "$0.00"},
    ])


def _base_refs():
    players = pd.DataFrame([{"Player_ID": p} for p in [1, 2, 3, 99]])
    users = pd.DataFrame([{"OwnerID": 10}])
    positions = pd.DataFrame([{"PositionID": 4, "Position": "WR"}])
    return players, users, positions


def test_keeper_labeling_flags_bids_at_or_below_threshold():
    players, users, positions = _base_refs()
    validated_df, _, report = validate_historical_draft_results(
        _base_draft(), players_df=players, users_df=users, positions_df=positions
    )
    assert "is_keeper" in validated_df.columns
    # bids $1 and $0 should be keepers; $50 should not
    keeper_rows = validated_df[validated_df["is_keeper"]]
    non_keeper_rows = validated_df[~validated_df["is_keeper"]]
    assert len(keeper_rows) == 2
    assert len(non_keeper_rows) == 1
    assert report["keeper_count"] == 2


def test_keeper_labeling_no_keepers_above_threshold():
    players, users, positions = _base_refs()
    draft = pd.DataFrame([
        {"PlayerID": 1, "OwnerID": 10, "Year": 2021, "PositionID": 4, "TeamID": 1, "WinningBid": "$50.00"},
        {"PlayerID": 2, "OwnerID": 10, "Year": 2021, "PositionID": 4, "TeamID": 1, "WinningBid": "$25.00"},
    ])
    players2 = pd.DataFrame([{"Player_ID": p} for p in [1, 2]])
    validated_df, _, report = validate_historical_draft_results(
        draft, players_df=players2, users_df=users, positions_df=positions
    )
    assert report["keeper_count"] == 0
    assert validated_df["is_keeper"].sum() == 0


def test_position_resolution_fills_null_position_from_canonical():
    players, users, positions = _base_refs()
    # Row with null PositionID for player 99 — should be resolved from canonical
    draft = pd.DataFrame([
        {"PlayerID": 99, "OwnerID": 10, "Year": 2021, "PositionID": None, "TeamID": 1, "WinningBid": "$20.00"},
    ])
    canonical = pd.DataFrame([
        {"player_id": 99, "source_position_id": "4.0", "canonical_position": "WR"},
    ])
    validated_df, correction_df, report = validate_historical_draft_results(
        draft, players_df=players, users_df=users, positions_df=positions,
        canonical_players_df=canonical,
    )
    # Row should be valid (resolved) not errored
    assert report["error_count"] == 0
    assert report["position_resolved_count"] == 1
    assert len(validated_df) == 1
    assert int(validated_df.iloc[0]["position_id"]) == 4
    # Correction ledger should record the resolution
    resolved = correction_df[correction_df["action"] == "position_resolved"]
    assert len(resolved) == 1


def test_position_null_without_canonical_stays_error():
    players, users, positions = _base_refs()
    draft = pd.DataFrame([
        {"PlayerID": 1, "OwnerID": 10, "Year": 2021, "PositionID": None, "TeamID": 1, "WinningBid": "$20.00"},
    ])
    validated_df, correction_df, report = validate_historical_draft_results(
        draft, players_df=players, users_df=users, positions_df=positions,
        canonical_players_df=None,
    )
    assert report["error_count"] >= 1
    assert report["error_breakdown"].get("invalid_position_id", 0) >= 1
    assert len(validated_df) == 0
    excluded = correction_df[correction_df["action"] == "excluded"]
    assert len(excluded) == 1


def test_year_completeness_flags_short_year():
    players, users, positions = _base_refs()
    # All 3 picks land in the same year — very short draft
    validated_df, _, report = validate_historical_draft_results(
        _base_draft(), players_df=players, users_df=users, positions_df=positions
    )
    yc = report["year_completeness"]
    assert 2021 in yc["years"]
    # 3 picks is below EXPECTED_PICKS_MIN (130) so it should be flagged
    flagged = [f["year"] for f in yc["flagged_years"]]
    assert 2021 in flagged


def test_year_completeness_passes_normal_year():
    """A year with exactly 145 valid picks should NOT appear in flagged_years."""
    from etl.transform.historical_draft_validator import EXPECTED_PICKS_MIN, EXPECTED_PICKS_MAX

    rows = [
        {"PlayerID": i, "OwnerID": 10, "Year": 2022, "PositionID": 4, "TeamID": 1, "WinningBid": f"${i}.00"}
        for i in range(1, 146)  # 145 picks
    ]
    draft = pd.DataFrame(rows)
    players_big = pd.DataFrame([{"Player_ID": i} for i in range(1, 146)])
    users = pd.DataFrame([{"OwnerID": 10}])
    positions = pd.DataFrame([{"PositionID": 4, "Position": "WR"}])
    _, _, report = validate_historical_draft_results(
        draft, players_df=players_big, users_df=users, positions_df=positions
    )
    yc = report["year_completeness"]
    assert EXPECTED_PICKS_MIN <= yc["years"][2022] <= EXPECTED_PICKS_MAX
    flagged_years = [f["year"] for f in yc["flagged_years"]]
    assert 2022 not in flagged_years


def test_correction_ledger_logs_excluded_rows():
    players, users, positions = _base_refs()
    draft = pd.DataFrame([
        # Valid row
        {"PlayerID": 1, "OwnerID": 10, "Year": 2021, "PositionID": 4, "TeamID": 1, "WinningBid": "$10.00"},
        # Invalid — bad player, owner, position
        {"PlayerID": -1, "OwnerID": -1, "Year": 2021, "PositionID": -1, "TeamID": 1, "WinningBid": "$5.00"},
    ])
    _, correction_df, report = validate_historical_draft_results(
        draft, players_df=players, users_df=users, positions_df=positions
    )
    excluded = correction_df[correction_df["action"] == "excluded"]
    assert len(excluded) == 1
    # Reason should mention the issues
    assert "invalid_player_id" in excluded.iloc[0]["reason"]


def test_report_includes_year_completeness_and_keeper_count():
    players, users, positions = _base_refs()
    _, _, report = validate_historical_draft_results(
        _base_draft(), players_df=players, users_df=users, positions_df=positions
    )
    assert "year_completeness" in report
    assert "keeper_count" in report
    assert "position_resolved_count" in report
