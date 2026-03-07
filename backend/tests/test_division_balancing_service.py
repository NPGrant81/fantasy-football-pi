from backend.services.division_balancing_service import (
    TeamStrengthInput,
    compute_confidence_score,
    compute_imbalance_pct,
    compute_team_strength,
    deterministic_balanced_assignment,
    deterministic_random_assignment,
    validate_division_math,
)


def test_strength_formula_with_projection_blend():
    row = TeamStrengthInput(
        team_id=10,
        avg_points_for_last_season=120.0,
        win_pct_last_season=0.75,
        projected_roster_score=130.0,
    )

    result = compute_team_strength(row)

    assert result.team_id == 10
    # raw = (120*0.6) + (0.75*40) = 72 + 30 = 102
    assert result.strength_raw == 102.0
    # final = (102*0.8) + (130*0.2) = 81.6 + 26 = 107.6
    assert result.strength_final == 107.6


def test_division_math_allows_odd_count_when_evenly_divisible():
    # 15 teams / 3 divisions = 5 teams/division -> valid under confirmed rule.
    errors = validate_division_math(team_count=15, division_count=3)
    assert errors == []


def test_division_math_blocks_under_three_per_division():
    errors = validate_division_math(team_count=10, division_count=5)
    assert errors
    assert "at least 3 teams" in errors[0]


def test_deterministic_assignments_stable_for_same_seed():
    team_ids = [1, 2, 3, 4, 5, 6]
    first = deterministic_random_assignment(team_ids, division_count=2, seed="seed-A")
    second = deterministic_random_assignment(team_ids, division_count=2, seed="seed-A")
    assert first == second


def test_confidence_decreases_with_imbalance():
    imbalance_low = compute_imbalance_pct({0: 100.0, 1: 98.0})
    imbalance_high = compute_imbalance_pct({0: 120.0, 1: 80.0})

    low_conf = compute_confidence_score(imbalance_low)
    high_conf = compute_confidence_score(imbalance_high)

    assert high_conf < low_conf


def test_balanced_assignment_snake_distribution():
    strengths = [
        compute_team_strength(TeamStrengthInput(team_id=1, avg_points_for_last_season=150, win_pct_last_season=0.9)),
        compute_team_strength(TeamStrengthInput(team_id=2, avg_points_for_last_season=140, win_pct_last_season=0.8)),
        compute_team_strength(TeamStrengthInput(team_id=3, avg_points_for_last_season=130, win_pct_last_season=0.7)),
        compute_team_strength(TeamStrengthInput(team_id=4, avg_points_for_last_season=120, win_pct_last_season=0.6)),
    ]

    assignment = deterministic_balanced_assignment(strengths, division_count=2, seed="snake")
    assert set(assignment.keys()) == {0, 1}
    assert len(assignment[0]) == 2
    assert len(assignment[1]) == 2
