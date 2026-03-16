import csv

from backend.scripts.prepare_mfl_draft_backfill_sheet import run_prepare_mfl_draft_backfill_sheet


def _write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_prepare_backfill_sheet_prefers_manual_rows_and_classifies_snake(tmp_path):
    root = tmp_path / "staged"

    _write_csv(
        root / "franchises" / "2002.csv",
        ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0010", "franchise_name": "Pugs are funny", "owner_name": "Pugs are funny"}],
    )
    _write_csv(
        root / "players" / "2002.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [{"season": "2002", "league_id": "29721", "player_mfl_id": "0501", "player_name": "Bills, Buffalo", "position": "Def", "nfl_team": "BUF"}],
    )
    _write_csv(
        root / "draftResults" / "2002.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id", "round", "pick_number", "draft_style"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0010", "player_mfl_id": "", "round": "01", "pick_number": "01", "draft_style": "snake"}],
    )
    _write_csv(
        root / "manual_overrides" / "draftResults" / "2002.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id", "round", "pick_number"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0010", "player_mfl_id": "", "round": "01", "pick_number": "01"}],
    )

    summary = run_prepare_mfl_draft_backfill_sheet(
        input_root=str(root),
        start_year=2002,
        end_year=2002,
    )

    assert summary["sheets_written"] == 1
    assert summary["rows_written"] == 1
    assert summary["style_counts"]["snake"] == 1

    out_path = root / "manual_overrides" / "draft_backfill_sheets" / "2002.csv"
    with out_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["franchise_name"] == "Pugs are funny"
    assert rows[0]["draft_style"] == "snake"
    assert rows[0]["hint_strategy"].startswith("Use season draft board order")


def test_prepare_backfill_sheet_classifies_auction_and_skips_filled_by_default(tmp_path):
    root = tmp_path / "staged"

    _write_csv(
        root / "franchises" / "2017.csv",
        ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
        [{"season": "2017", "league_id": "38909", "franchise_id": "0007", "franchise_name": "Team A", "owner_name": "Alpha"}],
    )
    _write_csv(
        root / "players" / "2017.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [{"season": "2017", "league_id": "38909", "player_mfl_id": "12625", "player_name": "Player A", "position": "QB", "nfl_team": "BUF"}],
    )
    _write_csv(
        root / "draftResults" / "2017.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id", "winning_bid", "draft_style"],
        [
            {"season": "2017", "league_id": "38909", "franchise_id": "0007", "player_mfl_id": "", "winning_bid": "42", "draft_style": "auction"},
            {"season": "2017", "league_id": "38909", "franchise_id": "0007", "player_mfl_id": "12625", "winning_bid": "44", "draft_style": "auction"},
        ],
    )

    summary = run_prepare_mfl_draft_backfill_sheet(
        input_root=str(root),
        start_year=2017,
        end_year=2017,
    )

    assert summary["rows_written"] == 1
    assert summary["rows_skipped_already_filled"] == 1
    assert summary["style_counts"]["auction"] == 1

    out_path = root / "manual_overrides" / "draft_backfill_sheets" / "2017.csv"
    with out_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["draft_style"] == "auction"
    assert rows[0]["hint_strategy"].startswith("Use auction ledger")
