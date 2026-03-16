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
    assert staged_rows == [
        {"season": "2009", "league_id": "24809", "franchise_id": "0001", "player_mfl_id": "1001"}
    ]

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
