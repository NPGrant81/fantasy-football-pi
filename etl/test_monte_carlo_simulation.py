import pandas as pd

from etl.transform.monte_carlo_simulation import SimulationConfig, run_monte_carlo_draft_simulation


def _sample_draft_results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"PlayerID": 101, "OwnerID": 1, "Year": 2024, "PositionID": 8002, "WinningBid": "$20"},
            {"PlayerID": 102, "OwnerID": 1, "Year": 2024, "PositionID": 8003, "WinningBid": "$40"},
            {"PlayerID": 103, "OwnerID": 2, "Year": 2024, "PositionID": 8004, "WinningBid": "$35"},
            {"PlayerID": 104, "OwnerID": 2, "Year": 2024, "PositionID": 8005, "WinningBid": "$15"},
            {"PlayerID": 105, "OwnerID": 3, "Year": 2024, "PositionID": 8003, "WinningBid": "$28"},
            {"PlayerID": 106, "OwnerID": 3, "Year": 2024, "PositionID": 8004, "WinningBid": "$22"},
            {"PlayerID": 107, "OwnerID": 4, "Year": 2024, "PositionID": 8099, "WinningBid": "$1"},
            {"PlayerID": 108, "OwnerID": 4, "Year": 2024, "PositionID": 8006, "WinningBid": "$3"},
        ]
    )


def _sample_players() -> pd.DataFrame:
    players = []
    base_id = 100
    positions = [8002, 8003, 8004, 8005, 8006, 8099]
    for index in range(1, 97):
        position_id = positions[(index - 1) % len(positions)]
        players.append(
            {
                "Player_ID": base_id + index,
                "PlayerName": f"Player {base_id + index}",
                "PositionID": position_id,
            }
        )
    return pd.DataFrame(players)


def _sample_rankings(players_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rank, row in enumerate(players_df.itertuples(index=False), start=1):
        rows.append(
            {
                "season": 2026,
                "rank": rank,
                "player_id": int(row.Player_ID),
                "player_name": row.PlayerName,
                "position": "QB" if row.PositionID == 8002 else "RB" if row.PositionID == 8003 else "WR" if row.PositionID == 8004 else "TE" if row.PositionID == 8005 else "DEF" if row.PositionID == 8006 else "K",
                "predicted_auction_value": max(1.0, 80 - rank * 0.5),
                "model_score": max(0.1, 55 - rank * 0.3),
            }
        )
    return pd.DataFrame(rows)


def _sample_budgets() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"DraftBudget": "$200", "OwnerID": 1},
            {"DraftBudget": "$200", "OwnerID": 2},
            {"DraftBudget": "$200", "OwnerID": 3},
            {"DraftBudget": "$200", "OwnerID": 4},
        ]
    )


def test_simulation_enforces_unique_players_and_budget_constraints():
    players = _sample_players()
    rankings = _sample_rankings(players)
    config = SimulationConfig(iterations=5, seed=7, teams_count=4, roster_size=10, target_owner_id=1)

    result = run_monte_carlo_draft_simulation(
        draft_results_df=_sample_draft_results(),
        players_df=players,
        historical_rankings_df=rankings,
        budget_df=_sample_budgets(),
        yearly_results_df=pd.DataFrame(),
        config=config,
    )

    duplicate_counts = result.draft_picks.groupby(["iteration", "player_id"]).size()
    assert duplicate_counts.max() == 1

    by_owner_iteration = result.team_metrics.groupby(["iteration", "owner_id"], as_index=False).first()
    assert (by_owner_iteration["budget_remaining"] >= 0).all()
    assert (by_owner_iteration["total_spend"] <= 200).all()


def test_simulation_fills_rosters_for_all_teams_each_iteration():
    players = _sample_players()
    rankings = _sample_rankings(players)
    config = SimulationConfig(
        iterations=3,
        seed=99,
        teams_count=4,
        roster_size=8,
        target_owner_id=1,
        position_limits={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DEF": 1, "K": 1},
    )

    result = run_monte_carlo_draft_simulation(
        draft_results_df=_sample_draft_results(),
        players_df=players,
        historical_rankings_df=rankings,
        budget_df=_sample_budgets(),
        yearly_results_df=pd.DataFrame(),
        config=config,
    )

    roster_sizes = result.team_metrics.groupby(["iteration", "owner_id"], as_index=False)["roster_size"].max()
    assert (roster_sizes["roster_size"] == 8).all()


def test_owner_summary_contains_owner_1_distributions_and_target_probabilities():
    players = _sample_players()
    rankings = _sample_rankings(players)
    config = SimulationConfig(iterations=6, seed=11, teams_count=4, roster_size=8, target_owner_id=1)

    result = run_monte_carlo_draft_simulation(
        draft_results_df=_sample_draft_results(),
        players_df=players,
        historical_rankings_df=rankings,
        budget_df=_sample_budgets(),
        yearly_results_df=pd.DataFrame(),
        config=config,
    )

    assert not result.owner_summary.empty
    row = result.owner_summary.iloc[0]
    assert row["owner_id"] == 1
    assert row["expected_total_points"] > 0
    assert row["expected_spend_rb"] >= 0
    assert isinstance(row["key_target_probability_snapshot"], str)
    assert "predicted_auction_value" in result.draft_picks.columns
    assert result.draft_picks["predicted_auction_value"].notna().all()
    assert "winning_bid" in result.draft_picks.columns
    assert result.draft_picks["winning_bid"].notna().all()


def test_simulation_handles_missing_position_ids_in_draft_results():
    players = _sample_players()
    rankings = _sample_rankings(players)
    draft_results = _sample_draft_results().copy()
    draft_results.loc[0, "PositionID"] = None
    draft_results.loc[1, "PositionID"] = float("nan")

    config = SimulationConfig(iterations=2, seed=13, teams_count=4, roster_size=8, target_owner_id=1)

    result = run_monte_carlo_draft_simulation(
        draft_results_df=draft_results,
        players_df=players,
        historical_rankings_df=rankings,
        budget_df=_sample_budgets(),
        yearly_results_df=pd.DataFrame(),
        config=config,
    )

    assert not result.draft_picks.empty
    assert not result.team_metrics.empty