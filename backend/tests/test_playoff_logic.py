from utils import playoff_logic


def make_team(id_, seed, **kwargs):
    t = {"id": id_, "seed": seed}
    t.update(kwargs)
    return t


def test_tiebreaker_winner_basic():
    a = make_team("a", 1, points_for=100, head_to_head=1)
    b = make_team("b", 2, points_for=90, head_to_head=2)
    # priority list checks points_for first
    winner = playoff_logic.tiebreaker_winner(a, b, ["points_for", "head_to_head"])
    assert winner["id"] == "a"


def test_tiebreaker_winner_random_draw_is_numeric():
    # IDs 2 and 10 sort differently as strings ("10" < "2") than as hashes;
    # verify the result is stable (numeric hash comparison, not lexicographic).
    import hashlib
    a = make_team(2, 1, points_for=50)
    b = make_team(10, 2, points_for=50)
    # Production logic hashes a combined "seed:id" key for random_draw;
    # mirror that here so the expected_id matches the actual tiebreaker logic.
    a_key = f"{a['seed']}:{a['id']}"
    b_key = f"{b['seed']}:{b['id']}"
    expected_id = a["id"] if (
        int(hashlib.sha256(a_key.encode()).hexdigest(), 16)
        > int(hashlib.sha256(b_key.encode()).hexdigest(), 16)
    ) else b["id"]
    winner = playoff_logic.tiebreaker_winner(a, b, ["random_draw"])
    assert winner["id"] == expected_id
    # Calling again must return the same result (determinism check).
    assert playoff_logic.tiebreaker_winner(a, b, ["random_draw"])["id"] == expected_id


def test_tiebreaker_winner_seed_fallback():
    # equal stats, lower seed should win
    a = make_team("a", 3, points_for=50)
    b = make_team("b", 2, points_for=50)
    winner = playoff_logic.tiebreaker_winner(a, b, ["points_for"])
    assert winner["id"] == "b"


def test_build_initial_bracket_no_byes():
    teams = [make_team(f"t{i}", i) for i in range(1, 5)]  # 4 teams, seeds 1-4
    bracket = playoff_logic.build_initial_bracket(teams, qualifiers=4)
    champs = bracket["championship"]
    assert len(champs) == 2  # two matches
    # first match seed1 vs seed4
    assert champs[0]["team_1"]["seed"] == 1
    assert champs[0]["team_2"]["seed"] == 4
    assert champs[0]["winner_to"] == "r2_m1"


def test_build_initial_bracket_with_byes():
    # 6 qualifiers, top 2 byes
    teams = [make_team(f"t{i}", i) for i in range(1, 7)]
    bracket = playoff_logic.build_initial_bracket(teams, qualifiers=6)
    champs = bracket["championship"]
    # should be 2 byes + 2 normal matches = 4 entries
    assert len(champs) == 4
    # first two are byes
    assert champs[0]["is_bye"]
    assert champs[1]["is_bye"]
    # third match should be seed3 vs seed6
    third = champs[2]
    assert third["team_1"]["seed"] == 3
    assert third["team_2"]["seed"] == 6
    # ensures winner_to slots propagate correctly
    assert champs[0]["winner_to"] == "r2_m1"
    assert champs[1]["winner_to"] == "r2_m1"
    assert champs[2]["winner_to"] == "r2_m2"
    assert champs[3]["winner_to"] == "r2_m2"


def test_build_initial_bracket_future_safe_8_team_structure():
    teams = [make_team(f"t{i}", i) for i in range(1, 9)]
    bracket = playoff_logic.build_initial_bracket(teams, qualifiers=8)
    champs = bracket["championship"]

    assert len(champs) == 4
    assert all(not match["is_bye"] for match in champs)
    assert [(match["team_1"]["seed"], match["team_2"]["seed"]) for match in champs] == [
        (1, 8),
        (2, 7),
        (3, 6),
        (4, 5),
    ]
    assert [match["winner_to"] for match in champs] == ["r2_m1", "r2_m1", "r2_m2", "r2_m2"]


def test_generate_round2_matches_basic():
    winners = [make_team("t3", 3), make_team("t5", 5)]
    byes = [make_team("t1", 1), make_team("t2", 2)]
    round2 = playoff_logic.generate_round2_matches(winners, byes)
    assert len(round2) == 2
    assert round2[0]["home_team"]["seed"] == 1
    assert round2[0]["away_team"]["seed"] == 5
    assert round2[1]["home_team"]["seed"] == 2
    assert round2[1]["away_team"]["seed"] == 3


def test_generate_consolation_bracket_even():
    all_teams = [make_team(f"t{i}", i) for i in range(1, 9)]
    playoff_teams = [make_team(f"t{i}", i) for i in range(1, 5)]
    cons = playoff_logic.generate_consolation_bracket(all_teams, playoff_teams)
    assert len(cons) == 2
    assert cons[0]["team_1"]["seed"] == 5
    assert cons[0]["team_2"]["seed"] == 8
    assert cons[1]["team_1"]["seed"] == 6
    assert cons[1]["team_2"]["seed"] == 7


def test_extract_winners_and_reseed():
    # create four matches, two completed, including a bye
    matches = [
        {"team_1": make_team("t1",1), "team_2": None, "team_1_score": None, "team_2_score": None, "is_bye": True},
        {"team_1": make_team("t2",2), "team_2": make_team("t3",3), "team_1_score": 80, "team_2_score": 90, "is_bye": False},
        {"team_1": make_team("t4",4), "team_2": make_team("t5",5), "team_1_score": 70, "team_2_score": 70, "is_bye": False},
        {"team_1": make_team("t6",6), "team_2": make_team("t7",7), "team_1_score": 100, "team_2_score": 50, "is_bye": False},
    ]
    # t4 vs t5 tie should go to higher seed (t4)
    winners, byes = playoff_logic.extract_round_winners(matches, ["points_for"])
    assert byes == [make_team("t1",1)]
    assert any(w["id"] == "t3" for w in winners)
    assert any(w["id"] == "t4" for w in winners)
    assert any(w["id"] == "t6" for w in winners)
    next_matches = playoff_logic.reseed_bracket(matches, ["points_for"])
    assert len(next_matches) == 2
    # ensure highest seed #1 paired with lowest winner seed
    assert next_matches[0]["home_team"]["seed"] == 1
