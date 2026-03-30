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
