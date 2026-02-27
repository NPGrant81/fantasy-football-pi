import pytest

from backend.utils.efficiency import calculate_optimal_score


def test_calculate_optimal_simple():
    settings = {"starting_slots": {"QB":1, "RB":2, "WR":2, "TE":1, "K":1, "DEF":1, "FLEX":1}}
    roster = [
        {"player_id": 1, "position": "QB", "actual_score": 20},
        {"player_id": 2, "position": "RB", "actual_score": 15},
        {"player_id": 3, "position": "RB", "actual_score": 10},
        {"player_id": 4, "position": "WR", "actual_score": 18},
        {"player_id": 5, "position": "WR", "actual_score": 12},
        {"player_id": 6, "position": "TE", "actual_score": 8},
        {"player_id": 7, "position": "K", "actual_score": 7},
        {"player_id": 8, "position": "DEF", "actual_score": 5},
        {"player_id": 9, "position": "RB", "actual_score": 9},  # candidate for flex
        {"player_id": 10, "position": "WR", "actual_score": 6},
    ]
    # best lineup would be QB20 + RB15+10 + WR18+12 + TE8 + K7 + DEF5 + FLEX9 = 104
    opt, lineup = calculate_optimal_score(roster, settings, return_lineup=True)
    assert pytest.approx(opt, rel=1e-3) == 104.0
    # lineup should include every starter + flex (total slots minus any K/DEF if zero)
    expected_slots = sum(settings['starting_slots'].values())
    assert len(lineup) == expected_slots


def test_calculate_optimal_excludes_ir_and_taxi():
    settings = {"starting_slots": {"QB":1, "RB":1, "WR":1, "TE":1, "K":0, "DEF":0, "FLEX":1}}
    roster = [
        {"player_id": 1, "position": "QB", "actual_score": 25, "is_ir": True},
        {"player_id": 2, "position": "QB", "actual_score": 10},
        {"player_id": 3, "position": "RB", "actual_score": 15},
        {"player_id": 4, "position": "WR", "actual_score": 20},
        {"player_id": 5, "position": "TE", "actual_score": 5},
        {"player_id": 6, "position": "RB", "actual_score": 12, "is_taxi": True},
    ]
    # best lineup should ignore player 1 and 6
    # QB=10, RB=15, WR=20, TE=5, FLEX=??? flex eligible RB/WR/TE next highest: none  (only RB/WR/TE left are 12 and IR/Taxi)
    opt, _ = calculate_optimal_score(roster, settings, return_lineup=True)
    # actual QB(10)+RB(15)+WR(20)+TE(5) = 50 (IR and taxi excluded)
    assert opt == 50.0


def test_calculate_optimal_missing_scores():
    settings = {"starting_slots": {"QB":1, "RB":1, "WR":1, "TE":0, "K":0, "DEF":0, "FLEX":1}}
    roster = [
        {"player_id": 1, "position": "QB"},
        {"player_id": 2, "position": "RB", "actual_score": 14},
        {"player_id": 3, "position": "WR", "actual_score": 9},
    ]
    # QB defaults to 0, flex picks RB14
    opt, _ = calculate_optimal_score(roster, settings, return_lineup=True)
    # optimal: QB0 + RB14 + WR9 = 23 (no additional flex eligible)
    assert opt == 23.0
