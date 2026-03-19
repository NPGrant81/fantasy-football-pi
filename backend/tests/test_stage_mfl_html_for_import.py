import csv
import json

from backend.scripts.stage_mfl_html_for_import import run_stage_mfl_html_for_import


def _write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def test_stage_mfl_html_for_import_copies_required_and_supplementary(tmp_path):
    api_root = tmp_path / "api"
    html_root = tmp_path / "html"
    output_root = tmp_path / "staged"

    _write_csv(
        api_root / "franchises" / "2002.csv",
        ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0001", "franchise_name": "A", "owner_name": "Alpha"}],
    )
    _write_csv(
        api_root / "players" / "2002.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [{"season": "2002", "league_id": "29721", "player_mfl_id": "1001", "player_name": "Player One", "position": "QB", "nfl_team": "BUF"}],
    )
    _write_csv(
        api_root / "draftResults" / "2002.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0001", "player_mfl_id": "1001"}],
    )

    _write_csv(
        html_root / "league_champions" / "2002.csv",
        ["season", "league_id", "champion"],
        [{"season": "2002", "league_id": "29721", "champion": "A"}],
    )

    (html_root / "_run_summary.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    summary = run_stage_mfl_html_for_import(
        start_year=2002,
        end_year=2002,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    assert summary["copied_required_files"] == 3
    assert summary["scaffolded_required_files"] == 0
    assert summary["copied_html_reports"] == 1
    assert summary["draft_results_manual_templates"] == 0

    assert (output_root / "franchises" / "2002.csv").exists()
    assert (output_root / "players" / "2002.csv").exists()
    assert (output_root / "draftResults" / "2002.csv").exists()
    assert (output_root / "supplementary_html" / "league_champions" / "2002.csv").exists()
    assert (output_root / "supplementary_html" / "_html_run_summary.json").exists()


def test_stage_mfl_html_for_import_scaffolds_when_api_missing(tmp_path):
    output_root = tmp_path / "staged"

    summary = run_stage_mfl_html_for_import(
        start_year=2003,
        end_year=2003,
        api_root=str(tmp_path / "missing_api"),
        html_root=str(tmp_path / "missing_html"),
        output_root=str(output_root),
        overwrite=True,
    )

    assert summary["copied_required_files"] == 0
    assert summary["scaffolded_required_files"] == 3
    assert summary["copied_html_reports"] == 0
    assert summary["draft_results_manual_templates"] == 1
    assert len(summary["warnings"]) >= 4

    for report_type in ("franchises", "players", "draftResults"):
        csv_path = output_root / report_type / "2003.csv"
        assert csv_path.exists()
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        assert len(rows) == 1

    manual_override = output_root / "manual_overrides" / "draftResults" / "2003.csv"
    assert manual_override.exists()


def test_stage_mfl_html_for_import_merges_existing_manual_draft_overrides(tmp_path):
    api_root = tmp_path / "api"
    html_root = tmp_path / "html"
    output_root = tmp_path / "staged"

    _write_csv(
        api_root / "franchises" / "2009.csv",
        ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
        [{"season": "2009", "league_id": "24809", "franchise_id": "0001", "franchise_name": "A", "owner_name": "Alpha"}],
    )
    _write_csv(
        api_root / "players" / "2009.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [{"season": "2009", "league_id": "24809", "player_mfl_id": "1001", "player_name": "Player One", "position": "QB", "nfl_team": "BUF"}],
    )
    _write_csv(
        api_root / "draftResults" / "2009.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id"],
        [],
    )
    html_root.mkdir(parents=True, exist_ok=True)

    first_summary = run_stage_mfl_html_for_import(
        start_year=2009,
        end_year=2009,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    assert first_summary["draft_results_manual_templates"] == 1
    manual_override = output_root / "manual_overrides" / "draftResults" / "2009.csv"
    assert manual_override.exists()

    _write_csv(
        manual_override,
        ["season", "league_id", "franchise_id", "player_mfl_id"],
        [{"season": "2009", "league_id": "24809", "franchise_id": "0001", "player_mfl_id": "1001"}],
    )

    second_summary = run_stage_mfl_html_for_import(
        start_year=2009,
        end_year=2009,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    assert second_summary["draft_results_manual_templates"] == 0
    assert second_summary["manual_override_rows_merged"] == 1

    with (output_root / "draftResults" / "2009.csv").open("r", encoding="utf-8", newline="") as handle:
        staged_rows = list(csv.DictReader(handle))
    assert len(staged_rows) == 1
    assert staged_rows[0]["season"] == "2009"
    assert staged_rows[0]["league_id"] == "24809"
    assert staged_rows[0]["franchise_id"] == "0001"
    assert staged_rows[0]["player_mfl_id"] == "1001"

    with manual_override.open("r", encoding="utf-8", newline="") as handle:
        manual_rows = list(csv.DictReader(handle))
    assert manual_rows == [
        {"season": "2009", "league_id": "24809", "franchise_id": "0001", "player_mfl_id": "1001"}
    ]


def test_stage_mfl_html_for_import_populates_manual_template_from_raw_draft_skeleton(tmp_path):
    api_root = tmp_path / "api"
    html_root = tmp_path / "html"
    output_root = tmp_path / "staged"

    _write_csv(
        api_root / "franchises" / "2002.csv",
        ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0001", "franchise_name": "A", "owner_name": "Alpha"}],
    )
    _write_csv(
        api_root / "players" / "2002.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [{"season": "2002", "league_id": "29721", "player_mfl_id": "1001", "player_name": "Player One", "position": "QB", "nfl_team": "BUF"}],
    )
    _write_csv(
        api_root / "league" / "2002.csv",
        ["season", "league_id"],
        [{"season": "2002", "league_id": "29721"}],
    )
    _write_csv(
        api_root / "draftResults" / "2002.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id"],
        [],
    )

    raw_payload = {
        "draftResults": {
            "draftUnit": {
                "draftPick": [
                    {"franchise": "0001", "round": "01", "pick": "01", "player": ""},
                    {"franchise": "0002", "round": "01", "pick": "02", "player": ""},
                ]
            }
        }
    }
    raw_path = api_root / "raw" / "draftResults" / "2002.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")
    html_root.mkdir(parents=True, exist_ok=True)

    summary = run_stage_mfl_html_for_import(
        start_year=2002,
        end_year=2002,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    assert summary["draft_results_manual_templates"] == 1
    assert summary["manual_override_rows_merged"] == 0
    assert any("2 skeleton rows" in warning for warning in summary["warnings"])

    manual_override = output_root / "manual_overrides" / "draftResults" / "2002.csv"
    with manual_override.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [
        {
            "season": "2002",
            "league_id": "29721",
            "franchise_id": "0001",
            "player_mfl_id": "",
            "round": "01",
            "pick_number": "01",
        },
        {
            "season": "2002",
            "league_id": "29721",
            "franchise_id": "0002",
            "player_mfl_id": "",
            "round": "01",
            "pick_number": "02",
        },
    ]


def test_stage_mfl_html_for_import_merge_preserves_existing_draft_metadata_columns(tmp_path):
    api_root = tmp_path / "api"
    html_root = tmp_path / "html"
    output_root = tmp_path / "staged"

    _write_csv(
        api_root / "franchises" / "2017.csv",
        ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
        [{"season": "2017", "league_id": "38909", "franchise_id": "0007", "franchise_name": "A", "owner_name": "Alpha"}],
    )
    _write_csv(
        api_root / "players" / "2017.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [{"season": "2017", "league_id": "38909", "player_mfl_id": "12625", "player_name": "Player One", "position": "QB", "nfl_team": "BUF"}],
    )
    _write_csv(
        api_root / "draftResults" / "2017.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id", "draft_source", "draft_style"],
        [],
    )
    html_root.mkdir(parents=True, exist_ok=True)

    run_stage_mfl_html_for_import(
        start_year=2017,
        end_year=2017,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    manual_override = output_root / "manual_overrides" / "draftResults" / "2017.csv"
    _write_csv(
        manual_override,
        ["season", "league_id", "franchise_id", "player_mfl_id"],
        [{"season": "2017", "league_id": "38909", "franchise_id": "0007", "player_mfl_id": "12625"}],
    )

    run_stage_mfl_html_for_import(
        start_year=2017,
        end_year=2017,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    with (output_root / "draftResults" / "2017.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert "draft_source" in (reader.fieldnames or [])
    assert "draft_style" in (reader.fieldnames or [])
    assert len(rows) == 1
    assert rows[0]["season"] == "2017"
    assert rows[0]["league_id"] == "38909"
    assert rows[0]["franchise_id"] == "0007"
    assert rows[0]["player_mfl_id"] == "12625"
    assert (rows[0].get("draft_source") or "").strip() == ""
    assert (rows[0].get("draft_style") or "").strip() == ""


def test_stage_mfl_html_for_import_merge_multi_row_overrides_no_key_collision(tmp_path):
    """Multiple manual override rows (distinct player_mfl_ids) all appear in the
    merged output — no row overwrites another via a shared key."""
    api_root = tmp_path / "api"
    html_root = tmp_path / "html"
    output_root = tmp_path / "staged"

    _write_csv(
        api_root / "franchises" / "2010.csv",
        ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
        [
            {"season": "2010", "league_id": "24810", "franchise_id": "0001", "franchise_name": "A", "owner_name": "Alpha"},
            {"season": "2010", "league_id": "24810", "franchise_id": "0002", "franchise_name": "B", "owner_name": "Beta"},
        ],
    )
    _write_csv(
        api_root / "players" / "2010.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [
            {"season": "2010", "league_id": "24810", "player_mfl_id": "2001", "player_name": "Player A", "position": "RB", "nfl_team": "NYG"},
            {"season": "2010", "league_id": "24810", "player_mfl_id": "2002", "player_name": "Player B", "position": "WR", "nfl_team": "DAL"},
        ],
    )
    # Staged draftResults starts empty (legacy season — no player_mfl_id populated).
    _write_csv(
        api_root / "draftResults" / "2010.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id"],
        [],
    )
    html_root.mkdir(parents=True, exist_ok=True)

    first_summary = run_stage_mfl_html_for_import(
        start_year=2010,
        end_year=2010,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    assert first_summary["draft_results_manual_templates"] == 1
    manual_override = output_root / "manual_overrides" / "draftResults" / "2010.csv"
    assert manual_override.exists()

    # Operator fills in two picks — different franchises and different player ids.
    _write_csv(
        manual_override,
        ["season", "league_id", "franchise_id", "player_mfl_id"],
        [
            {"season": "2010", "league_id": "24810", "franchise_id": "0001", "player_mfl_id": "2001"},
            {"season": "2010", "league_id": "24810", "franchise_id": "0002", "player_mfl_id": "2002"},
        ],
    )

    second_summary = run_stage_mfl_html_for_import(
        start_year=2010,
        end_year=2010,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    assert second_summary["manual_override_rows_merged"] == 2

    with (output_root / "draftResults" / "2010.csv").open("r", encoding="utf-8", newline="") as handle:
        staged_rows = list(csv.DictReader(handle))

    player_ids = {row["player_mfl_id"] for row in staged_rows}
    assert player_ids == {"2001", "2002"}, "Both override rows must be present — no key collision"
    assert len(staged_rows) == 2


def test_stage_mfl_html_for_import_merge_preserves_manual_only_optional_columns(tmp_path):
    api_root = tmp_path / "api"
    html_root = tmp_path / "html"
    output_root = tmp_path / "staged"

    _write_csv(
        api_root / "franchises" / "2018.csv",
        ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
        [{"season": "2018", "league_id": "38910", "franchise_id": "0003", "franchise_name": "Team C", "owner_name": "Gamma"}],
    )
    _write_csv(
        api_root / "players" / "2018.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [{"season": "2018", "league_id": "38910", "player_mfl_id": "3001", "player_name": "Player C", "position": "RB", "nfl_team": "BUF"}],
    )
    _write_csv(
        api_root / "draftResults" / "2018.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id"],
        [],
    )
    html_root.mkdir(parents=True, exist_ok=True)

    run_stage_mfl_html_for_import(
        start_year=2018,
        end_year=2018,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    manual_override = output_root / "manual_overrides" / "draftResults" / "2018.csv"
    _write_csv(
        manual_override,
        ["season", "league_id", "franchise_id", "player_mfl_id", "winning_bid", "is_keeper_pick"],
        [{"season": "2018", "league_id": "38910", "franchise_id": "0003", "player_mfl_id": "3001", "winning_bid": "44", "is_keeper_pick": "1"}],
    )

    run_stage_mfl_html_for_import(
        start_year=2018,
        end_year=2018,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    with (output_root / "draftResults" / "2018.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert "winning_bid" in (reader.fieldnames or [])
    assert "is_keeper_pick" in (reader.fieldnames or [])
    assert len(rows) == 1
    assert rows[0]["winning_bid"] == "44"
    assert rows[0]["is_keeper_pick"] == "1"


def test_stage_mfl_html_for_import_skeleton_infers_league_id_without_league_csv(tmp_path):
    api_root = tmp_path / "api"
    html_root = tmp_path / "html"
    output_root = tmp_path / "staged"

    _write_csv(
        api_root / "franchises" / "2002.csv",
        ["season", "league_id", "franchise_id", "franchise_name", "owner_name"],
        [{"season": "2002", "league_id": "29721", "franchise_id": "0001", "franchise_name": "A", "owner_name": "Alpha"}],
    )
    _write_csv(
        api_root / "players" / "2002.csv",
        ["season", "league_id", "player_mfl_id", "player_name", "position", "nfl_team"],
        [{"season": "2002", "league_id": "29721", "player_mfl_id": "1001", "player_name": "Player One", "position": "QB", "nfl_team": "BUF"}],
    )
    _write_csv(
        api_root / "draftResults" / "2002.csv",
        ["season", "league_id", "franchise_id", "player_mfl_id"],
        [],
    )

    raw_payload = {
        "draftResults": {
            "draftUnit": {
                "draftPick": [
                    {"franchise": "0001", "round": "01", "pick": "01", "player": ""},
                ]
            }
        }
    }
    raw_path = api_root / "raw" / "draftResults" / "2002.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")
    html_root.mkdir(parents=True, exist_ok=True)

    run_stage_mfl_html_for_import(
        start_year=2002,
        end_year=2002,
        api_root=str(api_root),
        html_root=str(html_root),
        output_root=str(output_root),
        overwrite=True,
    )

    manual_override = output_root / "manual_overrides" / "draftResults" / "2002.csv"
    with manual_override.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["league_id"] == "29721"
