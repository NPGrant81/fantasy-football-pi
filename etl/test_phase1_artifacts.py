import pandas as pd

from etl.transform.historical_draft_validator import validate_historical_draft_results
from etl.transform.owner_budget_timeline import build_owner_budget_timeline
from etl.transform.player_metadata_canonicalization import canonicalize_player_metadata


def test_player_metadata_canonicalization_is_deterministic_and_normalized():
    players = pd.DataFrame(
        [
            {"player_id": 1, "player_name": "CeeDee Lamb", "position": "WR", "nfl_team": "dal"},
            {"player_id": 1, "player_name": "Cee Dee Lamb", "position": "WR", "nfl_team": "DAL"},
            {"player_id": 2, "player_name": "Cowboys DST", "position": "d/st", "nfl_team": "DAL"},
        ]
    )
    aliases = {"cee dee lamb": "CeeDee Lamb"}

    first = canonicalize_player_metadata(players, aliases)
    second = canonicalize_player_metadata(players.sample(frac=1.0, random_state=7), aliases)

    assert len(first.canonical_players) == 2
    assert first.run_report["digest"] == second.run_report["digest"]
    assert set(first.canonical_players["position"].tolist()) == {"WR", "DEF"}
    assert first.run_report["position_resolution_pct"] == 100.0


def test_owner_budget_timeline_builds_cumulative_spend_and_reconciliation():
    events = pd.DataFrame(
        [
            {"league_id": 1, "season": 2026, "owner_id": 10, "event_ts": "2026-08-01T00:00:00Z", "event_type": "draft_pick", "winning_bid": 20},
            {"league_id": 1, "season": 2026, "owner_id": 10, "event_ts": "2026-08-01T00:01:00Z", "event_type": "draft_pick", "winning_bid": 10},
            {"league_id": 1, "season": 2026, "owner_id": 11, "event_ts": "2026-08-01T00:02:00Z", "event_type": "draft_pick", "winning_bid": 15},
        ]
    )

    result = build_owner_budget_timeline(events, start_budget=200.0)

    assert len(result.timeline) == 3
    owner_10_rows = result.timeline[result.timeline["owner_id"] == 10].sort_values("event_ts")
    assert owner_10_rows.iloc[0]["remaining_budget"] == 180.0
    assert owner_10_rows.iloc[1]["remaining_budget"] == 170.0
    assert result.reconciliation_report["failed_rows"] == 0


def test_historical_draft_validator_flags_duplicates_and_missing_refs():
    draft = pd.DataFrame(
        [
            {"league_id": 1, "year": 2025, "owner_id": 10, "player_id": 100, "round_num": 1, "pick_num": 1, "is_keeper": False},
            {"league_id": 1, "year": 2025, "owner_id": 10, "player_id": 101, "round_num": 1, "pick_num": 1, "is_keeper": True},
            {"league_id": 1, "year": 2025, "owner_id": -1, "player_id": -1, "round_num": 2, "pick_num": 2, "is_keeper": False},
        ]
    )
    players = pd.DataFrame([{"id": 100}])
    owners = pd.DataFrame([{"id": 10}])

    result = validate_historical_draft_results(draft, players_df=players, owners_df=owners)

    assert result.validation_report["duplicate_pick_count"] == 2
    assert result.validation_report["critical_unresolved_reference_count"] >= 1
    assert result.validation_report["keeper_labeling_summary"]["keeper_rows"] == 1
    assert not result.correction_ledger.empty
