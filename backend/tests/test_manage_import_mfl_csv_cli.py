from click.testing import CliRunner
import pytest

import backend.manage as manage


@pytest.mark.parametrize(
    "argv",
    [
        ["import-mfl-csv", "--source-mode", "csv", "--target-league-id", "60", "--start-year", "2022", "--end-year", "2023"],
        ["reconcile-mfl-import", "--source-mode", "csv", "--target-league-id", "60", "--start-year", "2022", "--end-year", "2023"],
        ["stage-mfl-html-for-import", "--source-mode", "csv", "--start-year", "2024", "--end-year", "2024", "--output-root", "tmp/staged"],
        ["prepare-mfl-draft-backfill-sheet", "--source-mode", "csv", "--start-year", "2024", "--end-year", "2024", "--output-root", "tmp/sheets"],
        ["resolve-mfl-draft-backfill-names", "--source-mode", "csv", "--start-year", "2024", "--end-year", "2024", "--sheet-root", "tmp/sheets"],
        ["apply-mfl-draft-backfill-sheet", "--source-mode", "csv", "--start-year", "2024", "--end-year", "2024", "--sheet-root", "tmp/sheets"],
    ],
)
def test_csv_source_mode_is_rejected(argv):
    runner = CliRunner()
    result = runner.invoke(manage.cli, argv)

    assert result.exit_code != 0
    assert "Invalid value for '--source-mode'" in result.output


def test_import_mfl_csv_cli_db_mode_dry_run_with_source_league(monkeypatch):
    captured = {}

    def fake_run_import_mfl_csv(**kwargs):
        captured.update(kwargs)
        return {
            "files_checked": 5,
            "files_missing": 0,
            "rows_validated": 12,
            "rows_invalid": 0,
            "players_inserted": 1,
            "players_matched": 2,
            "draft_picks_inserted": 3,
            "draft_picks_skipped": 0,
            "matchups_inserted": 1,
            "matchups_skipped": 0,
            "bye_matchups_skipped": 0,
            "skipped_missing_owner_map": 0,
            "skipped_missing_player_map": 0,
        }

    monkeypatch.setattr(manage, "run_import_mfl_csv", fake_run_import_mfl_csv)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "import-mfl-csv",
            "--source-mode",
            "db",
            "--source-league-id",
            "11422",
            "--target-league-id",
            "60",
            "--start-year",
            "2022",
            "--end-year",
            "2023",
        ],
    )

    assert result.exit_code == 0
    assert "MFL import summary" in result.output
    assert "Source mode: db" in result.output
    assert "Source league id: 11422" in result.output

    assert captured["input_root"] is None
    assert captured["source_mode"] == "db"
    assert captured["source_league_id"] == "11422"
    assert captured["target_league_id"] == 60
    assert captured["start_year"] == 2022
    assert captured["end_year"] == 2023
    assert captured["dry_run"] is True


def test_reconcile_mfl_import_cli_db_mode_with_source_league(monkeypatch):
    captured = {}

    def fake_run_reconcile_mfl_import(**kwargs):
        captured.update(kwargs)
        return {
            "seasons": [2022, 2023],
            "mismatch_count": 0,
            "season_reports": [],
            "warnings": [],
        }

    monkeypatch.setattr(manage, "run_reconcile_mfl_import", fake_run_reconcile_mfl_import)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "reconcile-mfl-import",
            "--source-mode",
            "db",
            "--source-league-id",
            "11422",
            "--target-league-id",
            "60",
            "--start-year",
            "2022",
            "--end-year",
            "2023",
        ],
    )

    assert result.exit_code == 0
    assert "MFL import reconciliation summary" in result.output
    assert "Source mode: db" in result.output
    assert "Source league id: 11422" in result.output

    assert captured["input_root"] is None
    assert captured["source_mode"] == "db"
    assert captured["source_league_id"] == "11422"
    assert captured["target_league_id"] == 60
    assert captured["start_year"] == 2022
    assert captured["end_year"] == 2023


def test_stage_mfl_html_for_import_cli_db_mode_with_source_league(monkeypatch, tmp_path):
    captured = {}

    def fake_run_stage_mfl_html_for_import(**kwargs):
        captured.update(kwargs)
        return {
            "seasons": [2024, 2024],
            "copied_required_files": 3,
            "scaffolded_required_files": 0,
            "copied_html_reports": 0,
            "draft_results_manual_templates": 0,
            "manual_override_rows_merged": 0,
            "output_root": str(tmp_path / "staged"),
            "warnings": [],
        }

    monkeypatch.setattr(manage, "run_stage_mfl_html_for_import", fake_run_stage_mfl_html_for_import)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "stage-mfl-html-for-import",
            "--source-mode",
            "db",
            "--source-league-id",
            "11422",
            "--start-year",
            "2024",
            "--end-year",
            "2024",
            "--output-root",
            str(tmp_path / "staged"),
        ],
    )

    assert result.exit_code == 0
    assert "MFL staging summary" in result.output
    assert "Source mode: db" in result.output
    assert "Source league id: 11422" in result.output

    assert captured["source_mode"] == "db"
    assert captured["source_league_id"] == "11422"
    assert captured["api_root"] is None
    assert captured["html_root"] is None


def test_prepare_mfl_draft_backfill_sheet_cli_db_mode_with_source_league(monkeypatch, tmp_path):
    captured = {}

    def fake_run_prepare_mfl_draft_backfill_sheet(**kwargs):
        captured.update(kwargs)
        return {
            "seasons": [2024, 2024],
            "sheets_written": 1,
            "rows_written": 4,
            "rows_skipped_already_filled": 0,
            "style_counts": {"snake": 4},
            "output_root": str(tmp_path / "sheets"),
            "warnings": [],
        }

    monkeypatch.setattr(manage, "run_prepare_mfl_draft_backfill_sheet", fake_run_prepare_mfl_draft_backfill_sheet)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "prepare-mfl-draft-backfill-sheet",
            "--source-mode",
            "db",
            "--source-league-id",
            "11422",
            "--start-year",
            "2024",
            "--end-year",
            "2024",
            "--output-root",
            str(tmp_path / "sheets"),
        ],
    )

    assert result.exit_code == 0
    assert "MFL draft backfill sheet summary" in result.output
    assert "Source mode: db" in result.output
    assert "Source league id: 11422" in result.output

    assert captured["source_mode"] == "db"
    assert captured["source_league_id"] == "11422"
    assert captured["input_root"] is None


def test_resolve_mfl_draft_backfill_names_cli_db_mode_with_source_league(monkeypatch, tmp_path):
    captured = {}

    def fake_run_resolve_mfl_draft_backfill_names(**kwargs):
        captured.update(kwargs)
        return {
            "seasons": [2024, 2024],
            "rows_seen": 4,
            "rows_matched": 2,
            "rows_already_filled": 1,
            "rows_skipped_no_manual_name": 1,
            "rows_unmatched": 0,
            "rows_ambiguous": 0,
            "sheet_root": str(tmp_path / "sheets"),
            "warnings": [],
        }

    monkeypatch.setattr(manage, "run_resolve_mfl_draft_backfill_names", fake_run_resolve_mfl_draft_backfill_names)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "resolve-mfl-draft-backfill-names",
            "--source-mode",
            "db",
            "--source-league-id",
            "11422",
            "--start-year",
            "2024",
            "--end-year",
            "2024",
            "--sheet-root",
            str(tmp_path / "sheets"),
        ],
    )

    assert result.exit_code == 0
    assert "MFL draft backfill name resolve summary" in result.output
    assert "Source mode: db" in result.output
    assert "Source league id: 11422" in result.output

    assert captured["source_mode"] == "db"
    assert captured["source_league_id"] == "11422"
    assert captured["input_root"] is None


def test_apply_mfl_draft_backfill_sheet_cli_db_mode_with_source_league(monkeypatch, tmp_path):
    captured = {}

    def fake_run_apply_mfl_draft_backfill_sheet(**kwargs):
        captured.update(kwargs)
        return {
            "seasons": [2024, 2024],
            "sheets_missing": 0,
            "candidate_rows": 1,
            "rows_updated": 1,
            "rows_appended": 0,
            "rows_skipped_missing_player_id": 0,
            "rows_skipped_missing_source_url": 0,
            "rows_skipped_blocked_source_policy": 0,
            "sheet_root": str(tmp_path / "sheets"),
            "warnings": [],
        }

    monkeypatch.setattr(manage, "run_apply_mfl_draft_backfill_sheet", fake_run_apply_mfl_draft_backfill_sheet)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "apply-mfl-draft-backfill-sheet",
            "--source-mode",
            "db",
            "--source-league-id",
            "11422",
            "--start-year",
            "2024",
            "--end-year",
            "2024",
            "--sheet-root",
            str(tmp_path / "sheets"),
            "--apply",
        ],
    )

    assert result.exit_code == 0
    assert "MFL backfill sheet apply summary" in result.output
    assert "Source mode: db" in result.output
    assert "Source league id: 11422" in result.output

    assert captured["source_mode"] == "db"
    assert captured["source_league_id"] == "11422"
    assert captured["input_root"] is None


