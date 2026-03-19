import csv

from backend.scripts.resolve_mfl_draft_backfill_names import run_resolve_mfl_draft_backfill_names


def _write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_resolve_names_matches_single_candidate_in_apply_mode(tmp_path):
    root = tmp_path / "staged"

    _write_csv(
        root / "players" / "2005.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [
            {
                "season": "2005",
                "league_id": "20248",
                "player_mfl_id": "12345",
                "player_name": "Tomlinson, Ladainian",
                "position": "RB",
                "nfl_team": "SDC",
            }
        ],
    )
    _write_csv(
        root / "manual_overrides" / "draft_backfill_sheets" / "2005.csv",
        [
            "season",
            "league_id",
            "franchise_id",
            "draft_style",
            "round",
            "pick_number",
            "manual_player_name",
            "player_mfl_id",
            "player_name_hint",
            "position_hint",
            "nfl_team_hint",
        ],
        [
            {
                "season": "2005",
                "league_id": "20248",
                "franchise_id": "0001",
                "draft_style": "snake",
                "round": "01",
                "pick_number": "01",
                "manual_player_name": "Tomlinson, Ladainian SDC RB",
                "player_mfl_id": "",
                "player_name_hint": "",
                "position_hint": "",
                "nfl_team_hint": "",
            }
        ],
    )

    summary = run_resolve_mfl_draft_backfill_names(
        input_root=str(root),
        start_year=2005,
        end_year=2005,
        apply_changes=True,
    )

    assert summary["rows_matched"] == 1
    rows = _read_csv(root / "manual_overrides" / "draft_backfill_sheets" / "2005.csv")
    assert rows[0]["player_mfl_id"] == "12345"
    assert rows[0]["player_name_hint"] == "Tomlinson, Ladainian"


def test_resolve_names_records_ambiguous_when_name_only_collides(tmp_path):
    root = tmp_path / "staged"

    _write_csv(
        root / "players" / "2005.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [
            {
                "season": "2005",
                "league_id": "20248",
                "player_mfl_id": "111",
                "player_name": "Smith, Steve",
                "position": "WR",
                "nfl_team": "CAR",
            },
            {
                "season": "2005",
                "league_id": "20248",
                "player_mfl_id": "222",
                "player_name": "Smith, Steve",
                "position": "RB",
                "nfl_team": "NYG",
            },
        ],
    )
    _write_csv(
        root / "manual_overrides" / "draft_backfill_sheets" / "2005.csv",
        ["season", "league_id", "franchise_id", "round", "pick_number", "manual_player_name", "player_mfl_id"],
        [
            {
                "season": "2005",
                "league_id": "20248",
                "franchise_id": "0001",
                "round": "05",
                "pick_number": "01",
                "manual_player_name": "Smith, Steve",
                "player_mfl_id": "",
            }
        ],
    )

    summary = run_resolve_mfl_draft_backfill_names(
        input_root=str(root),
        start_year=2005,
        end_year=2005,
        apply_changes=False,
    )

    assert summary["rows_ambiguous"] == 1
    rows = _read_csv(root / "manual_overrides" / "draft_backfill_sheets" / "2005.csv")
    assert rows[0]["player_mfl_id"] == ""

    review_rows = _read_csv(root / "manual_overrides" / "draft_backfill_sheets" / "_backfill_name_resolve_review.csv")
    assert len(review_rows) == 1
    assert review_rows[0]["candidate_ids"] == "111 | 222"
    assert review_rows[0]["candidate_names"] == "Smith, Steve | Smith, Steve"
