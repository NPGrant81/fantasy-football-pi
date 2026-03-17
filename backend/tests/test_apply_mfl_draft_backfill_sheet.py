import csv

from backend.scripts.apply_mfl_draft_backfill_sheet import run_apply_mfl_draft_backfill_sheet


def _write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_apply_backfill_sheet_updates_manual_rows_in_apply_mode(tmp_path):
    root = tmp_path / "staged"
    sheet_root = root / "manual_overrides" / "draft_backfill_sheets"

    _write_csv(
        root / "manual_overrides" / "draftResults" / "2002.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id", "round", "pick_number"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0010", "player_mfl_id": "", "round": "01", "pick_number": "01"}],
    )
    _write_csv(
        sheet_root / "2002.csv",
        ["season", "league_id", "franchise_id", "round", "pick_number", "winning_bid", "player_mfl_id", "manual_source_url"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0010", "round": "01", "pick_number": "01", "winning_bid": "", "player_mfl_id": "0501", "manual_source_url": "https://example.test"}],
    )

    summary = run_apply_mfl_draft_backfill_sheet(
        input_root=str(root),
        start_year=2002,
        end_year=2002,
        apply_changes=True,
    )

    assert summary["candidate_rows"] == 1
    assert summary["rows_updated"] == 1
    updated_rows = _read_csv(root / "manual_overrides" / "draftResults" / "2002.csv")
    assert updated_rows[0]["player_mfl_id"] == "0501"


def test_apply_backfill_sheet_dry_run_does_not_write(tmp_path):
    root = tmp_path / "staged"
    sheet_root = root / "manual_overrides" / "draft_backfill_sheets"

    _write_csv(
        root / "manual_overrides" / "draftResults" / "2003.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id", "round", "pick_number"],
        [{"season": "2003", "league_id": "39069", "franchise_id": "0001", "player_mfl_id": "", "round": "", "pick_number": ""}],
    )
    _write_csv(
        sheet_root / "2003.csv",
        ["season", "league_id", "franchise_id", "round", "pick_number", "player_mfl_id", "manual_source_url"],
        [{"season": "2003", "league_id": "39069", "franchise_id": "0001", "round": "", "pick_number": "", "player_mfl_id": "0999", "manual_source_url": ""}],
    )

    summary = run_apply_mfl_draft_backfill_sheet(
        input_root=str(root),
        start_year=2003,
        end_year=2003,
        apply_changes=False,
    )

    assert summary["candidate_rows"] == 1
    assert summary["rows_updated"] == 1
    original_rows = _read_csv(root / "manual_overrides" / "draftResults" / "2003.csv")
    assert original_rows[0]["player_mfl_id"] == ""


def test_apply_backfill_sheet_can_require_source_url(tmp_path):
    root = tmp_path / "staged"
    sheet_root = root / "manual_overrides" / "draft_backfill_sheets"

    _write_csv(
        root / "manual_overrides" / "draftResults" / "2002.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id", "round", "pick_number"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0010", "player_mfl_id": "", "round": "01", "pick_number": "01"}],
    )
    _write_csv(
        sheet_root / "2002.csv",
        ["season", "league_id", "franchise_id", "round", "pick_number", "player_mfl_id", "manual_source_url"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0010", "round": "01", "pick_number": "01", "player_mfl_id": "0501", "manual_source_url": ""}],
    )

    summary = run_apply_mfl_draft_backfill_sheet(
        input_root=str(root),
        start_year=2002,
        end_year=2002,
        apply_changes=True,
        require_source_url=True,
    )

    assert summary["rows_skipped_missing_source_url"] == 1
    updated_rows = _read_csv(root / "manual_overrides" / "draftResults" / "2002.csv")
    assert updated_rows[0]["player_mfl_id"] == ""
