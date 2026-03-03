import pandas as pd

from etl.transform.historical_rankings import (
    build_historical_features,
    score_historical_rankings,
)


def test_build_historical_features_parses_currency_and_adds_metrics():
    draft_results = pd.DataFrame(
        [
            {"PlayerID": 1, "Year": 2021, "PositionID": 8003, "WinningBid": "$55.00"},
            {"PlayerID": 1, "Year": 2022, "PositionID": 8003, "WinningBid": "$48.00"},
            {"PlayerID": 2, "Year": 2021, "PositionID": 8004, "WinningBid": "$15.00"},
            {"PlayerID": 2, "Year": 2022, "PositionID": 8004, "WinningBid": "$17.00"},
        ]
    )
    players = pd.DataFrame(
        [
            {"Player_ID": 1, "PlayerName": "Elite RB", "PositionID": 8003},
            {"Player_ID": 2, "PlayerName": "Steady WR", "PositionID": 8004},
        ]
    )

    features = build_historical_features(draft_results, players)

    assert "position_scarcity_boost" in features.columns
    assert "consistency" in features.columns
    elite_rb = features[features["player_id"] == 1].iloc[0]
    assert elite_rb["avg_bid"] > 40
    assert elite_rb["position"] == "RB"


def test_score_historical_rankings_generates_rank_and_tier():
    features = pd.DataFrame(
        [
            {
                "player_id": 1,
                "player_name": "Elite RB",
                "position": "RB",
                "avg_bid": 52.0,
                "median_bid": 50.0,
                "max_bid": 60.0,
                "min_bid": 45.0,
                "bid_std": 4.0,
                "recent_3yr_avg": 54.0,
                "recent_3yr_max": 60.0,
                "trend_slope": 1.1,
                "appearances": 4,
                "position_scarcity_boost": 0.6,
                "consistency": 0.2,
            },
            {
                "player_id": 2,
                "player_name": "Steady WR",
                "position": "WR",
                "avg_bid": 18.0,
                "median_bid": 17.0,
                "max_bid": 22.0,
                "min_bid": 12.0,
                "bid_std": 2.0,
                "recent_3yr_avg": 19.0,
                "recent_3yr_max": 22.0,
                "trend_slope": 0.3,
                "appearances": 4,
                "position_scarcity_boost": 0.1,
                "consistency": 0.33,
            },
        ]
    )

    rankings = score_historical_rankings(features, target_season=2026)

    assert list(rankings["rank"]) == [1, 2]
    assert rankings.iloc[0]["player_id"] == 1
    assert rankings.iloc[0]["consensus_tier"] in {"S", "A", "B", "C", "D"}
    assert rankings.iloc[0]["predicted_auction_value"] > rankings.iloc[1]["predicted_auction_value"]
