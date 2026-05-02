import pandas as pd

from etl.transform.historical_draft_validator import validate_historical_draft_results
from etl.transform.owner_budget_timeline import (
    build_owner_behavior_features,
    build_owner_budget_timeline,
)
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
# build_owner_behavior_features
# ---------------------------------------------------------------------------

def _make_behavior_fixtures():
    """Minimal but realistic set of DataFrames for behavior feature tests."""
    draft_budget = pd.DataFrame([
        {"OwnerID": 10, "Year": 2025, "DraftBudget": 200},
        {"OwnerID": 11, "Year": 2025, "DraftBudget": 200},
    ])
    # Owner 10 spends $100 on QB, $60 on RB, $40 on WR (total 200)
    # Owner 11 spends $80 on RB, $20 on TE (total 100)
    draft_results = pd.DataFrame([
        {"PlayerID": 1001, "OwnerID": 10, "Year": 2025, "WinningBid": "$100.00", "PositionID": 8002},
        {"PlayerID": 1002, "OwnerID": 10, "Year": 2025, "WinningBid": "$60.00",  "PositionID": 8003},
        {"PlayerID": 1003, "OwnerID": 10, "Year": 2025, "WinningBid": "$40.00",  "PositionID": 8004},
        {"PlayerID": 1004, "OwnerID": 11, "Year": 2025, "WinningBid": "$80.00",  "PositionID": 8003},
        {"PlayerID": 1005, "OwnerID": 11, "Year": 2025, "WinningBid": "$20.00",  "PositionID": 8005},
    ])
    users = pd.DataFrame([
        {"OwnerID": 10, "OwnerName": "Alice"},
        {"OwnerID": 11, "OwnerName": "Bob"},
    ])
    positions = pd.DataFrame([
        {"PositionID": 8002, "Position": "QB"},
        {"PositionID": 8003, "Position": "RB"},
        {"PositionID": 8004, "Position": "WR"},
        {"PositionID": 8005, "Position": "TE"},
    ])
    return draft_budget, draft_results, users, positions


def test_build_owner_behavior_features_returns_one_row_per_owner_season():
    draft_budget, draft_results, users, positions = _make_behavior_fixtures()
    timeline, _ = build_owner_budget_timeline(draft_budget, draft_results, users)
    behavior_df, report = build_owner_behavior_features(timeline, draft_results, positions)

    assert len(behavior_df) == 2
    assert report["owner_season_pairs"] == 2
    assert set(behavior_df["owner_id"].tolist()) == {10, 11}


def test_build_owner_behavior_features_positional_spend_sums_to_total():
    draft_budget, draft_results, users, positions = _make_behavior_fixtures()
    timeline, _ = build_owner_budget_timeline(draft_budget, draft_results, users)
    behavior_df, _ = build_owner_behavior_features(timeline, draft_results, positions)

    owner10 = behavior_df[behavior_df["owner_id"] == 10].iloc[0]
    pos_spend = owner10["spend_by_position"]
    assert abs(sum(pos_spend.values()) - float(owner10["total_spend"])) < 0.01
    assert pos_spend["QB"] == 100.0
    assert pos_spend["RB"] == 60.0


def test_build_owner_behavior_features_position_spend_pct_sums_to_one():
    draft_budget, draft_results, users, positions = _make_behavior_fixtures()
    timeline, _ = build_owner_budget_timeline(draft_budget, draft_results, users)
    behavior_df, _ = build_owner_behavior_features(timeline, draft_results, positions)

    for _, row in behavior_df.iterrows():
        pct_sum = sum(row["position_spend_pct"].values())
        assert abs(pct_sum - 1.0) < 1e-4, f"owner {row['owner_id']} pct sum={pct_sum}"


def test_build_owner_behavior_features_aggressiveness_index_between_0_and_1():
    draft_budget, draft_results, users, positions = _make_behavior_fixtures()
    timeline, _ = build_owner_budget_timeline(draft_budget, draft_results, users)
    behavior_df, _ = build_owner_behavior_features(timeline, draft_results, positions)

    owner10 = behavior_df[behavior_df["owner_id"] == 10].iloc[0]
    agg = owner10["aggressiveness_index"]
    assert agg is not None
    assert 0.0 <= agg <= 1.0
    # Owner 10 has 3 picks; top quartile = 1 pick ($100 of $200 = 0.5)
    assert abs(agg - 0.5) < 1e-4


def test_build_owner_behavior_features_positional_bias_index_non_negative():
    draft_budget, draft_results, users, positions = _make_behavior_fixtures()
    timeline, _ = build_owner_budget_timeline(draft_budget, draft_results, users)
    behavior_df, _ = build_owner_behavior_features(timeline, draft_results, positions)

    for _, row in behavior_df.iterrows():
        pbi = row["positional_bias_index"]
        assert pbi is not None
        assert pbi >= 0.0, f"owner {row['owner_id']} pbi={pbi}"


def test_build_owner_behavior_features_empty_input_returns_empty_df():
    empty_dr = pd.DataFrame(columns=["PlayerID", "OwnerID", "Year", "WinningBid", "PositionID"])
    positions = pd.DataFrame([{"PositionID": 8002, "Position": "QB"}])
    timeline = pd.DataFrame()
    behavior_df, report = build_owner_behavior_features(timeline, empty_dr, positions)

    assert behavior_df.empty
    assert report["owner_season_pairs"] == 0
    assert report["behavior_rows"] == 0


def test_build_owner_behavior_features_is_idempotent():
    """Running twice on identical input produces byte-equivalent output."""
    draft_budget, draft_results, users, positions = _make_behavior_fixtures()
    timeline, _ = build_owner_budget_timeline(draft_budget, draft_results, users)

    df1, r1 = build_owner_behavior_features(timeline, draft_results, positions)
    df2, r2 = build_owner_behavior_features(timeline, draft_results, positions)

    assert df1.to_csv(index=False) == df2.to_csv(index=False)
    assert r1["owner_season_pairs"] == r2["owner_season_pairs"]
