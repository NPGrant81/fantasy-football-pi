from backend.services.live_scoring_contract import (
    inspect_scoreboard_contract,
    map_scoreboard_payload,
    to_nfl_game_upsert_rows,
)


def _sample_scoreboard_payload() -> dict:
    return {
        "events": [
            {
                "id": "401772001",
                "season": {"year": 2026},
                "competitions": [
                    {
                        "date": "2026-09-10T20:20:00Z",
                        "week": {"number": 1},
                        "status": {"type": {"name": "in"}},
                        "competitors": [
                            {
                                "homeAway": "away",
                                "score": "17",
                                "team": {"id": "9", "abbreviation": "LAR"},
                                "leaders": [
                                    {
                                        "name": "fantasyPoints",
                                        "leaders": [
                                            {
                                                "value": 14.5,
                                                "athlete": {
                                                    "id": "2001",
                                                    "displayName": "Away QB",
                                                    "position": {"abbreviation": "QB"},
                                                },
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "homeAway": "home",
                                "score": "24",
                                "team": {"id": "2", "abbreviation": "BUF"},
                                "leaders": [
                                    {
                                        "name": "passingYards",
                                        "leaders": [
                                            {
                                                "value": 311,
                                                "athlete": {
                                                    "id": "1001",
                                                    "displayName": "Home QB",
                                                    "position": {"abbreviation": "QB"},
                                                },
                                            }
                                        ],
                                    },
                                    {
                                        "name": "fantasyPoints",
                                        "leaders": [
                                            {
                                                "value": 26.4,
                                                "athlete": {
                                                    "id": "1001",
                                                    "displayName": "Home QB",
                                                    "position": {"abbreviation": "QB"},
                                                },
                                            }
                                        ],
                                    },
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }


def test_inspect_scoreboard_contract_happy_path():
    report = inspect_scoreboard_contract(_sample_scoreboard_payload())
    assert report.event_count == 1
    assert report.missing_paths == []
    assert all(report.required_paths.values())


def test_inspect_scoreboard_contract_reports_missing_paths():
    payload = {"events": [{"id": "401772002", "competitions": []}]}
    report = inspect_scoreboard_contract(payload)
    assert report.event_count == 1
    assert "events[].season.year" in report.missing_paths
    assert "events[].competitions[].competitors[].score" in report.missing_paths


def test_map_scoreboard_payload_normalizes_home_away_and_scores():
    normalized = map_scoreboard_payload(_sample_scoreboard_payload())
    assert len(normalized.games) == 1

    game = normalized.games[0]
    assert game.event_id == "401772001"
    assert game.season == 2026
    assert game.week == 1
    assert game.status == "IN"
    assert game.home_team_id == 2
    assert game.away_team_id == 9
    assert game.home_team_abbr == "BUF"
    assert game.away_team_abbr == "LAR"
    assert game.home_score == 24
    assert game.away_score == 17


def test_map_scoreboard_payload_respects_overrides():
    normalized = map_scoreboard_payload(
        _sample_scoreboard_payload(),
        season_override=2030,
        week_override=7,
    )
    game = normalized.games[0]
    assert game.season == 2030
    assert game.week == 7


def test_to_nfl_game_upsert_rows_shapes_db_payload():
    normalized = map_scoreboard_payload(_sample_scoreboard_payload())
    rows = to_nfl_game_upsert_rows(normalized)

    assert len(rows) == 1
    assert rows[0]["event_id"] == "401772001"
    assert rows[0]["home_team_id"] == 2
    assert rows[0]["away_team_id"] == 9
    assert rows[0]["home_score"] == 24
    assert rows[0]["away_score"] == 17
    assert rows[0]["kickoff"] == "2026-09-10T20:20:00+00:00"


def test_map_scoreboard_payload_extracts_player_stats_from_leaders():
    normalized = map_scoreboard_payload(_sample_scoreboard_payload())

    assert len(normalized.player_stats) == 2

    home_qb = next(item for item in normalized.player_stats if item.player_espn_id == "1001")
    assert home_qb.player_name == "Home QB"
    assert home_qb.team_abbr == "BUF"
    assert home_qb.position == "QB"
    assert home_qb.fantasy_points == 26.4
    assert home_qb.stats["passingyards"] == 311.0
    assert home_qb.stats["fantasypoints"] == 26.4

    away_qb = next(item for item in normalized.player_stats if item.player_espn_id == "2001")
    assert away_qb.team_abbr == "LAR"
    assert away_qb.fantasy_points == 14.5
