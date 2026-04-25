from click.testing import CliRunner

import backend.manage as manage


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


def test_import_mfl_csv_cli_csv_mode_requires_input_root():
    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "import-mfl-csv",
            "--source-mode",
            "csv",
            "--target-league-id",
            "60",
            "--start-year",
            "2022",
            "--end-year",
            "2023",
        ],
    )

    assert result.exit_code != 0
    assert "--input-root is required when --source-mode=csv" in result.output


def test_bootstrap_mfl_franchise_users_requires_source_season_or_csv():
    """Invoking bootstrap without any source flag must error and direct user to --source-season."""
    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "bootstrap-mfl-franchise-users",
            "--target-league-id",
            "60",
        ],
    )
    assert result.exit_code != 0
    assert "--source-season is required" in result.output


def test_bootstrap_mfl_franchise_users_rejects_both_sources(tmp_path):
    """Providing both --franchises-csv and --source-season must error."""
    csv_file = tmp_path / "franchises.csv"
    csv_file.write_text("season,league_id,franchise_id,franchise_name,owner_name\n")
    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "bootstrap-mfl-franchise-users",
            "--franchises-csv",
            str(csv_file),
            "--source-season",
            "2023",
            "--target-league-id",
            "60",
        ],
    )
    assert result.exit_code != 0
    assert "Choose one input source" in result.output


def test_import_mfl_csv_default_source_mode_is_db(monkeypatch):
    """import-mfl-csv should default to db mode without requiring --source-mode."""
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {
            "files_checked": 0, "files_missing": 0, "rows_validated": 0,
            "rows_invalid": 0, "players_inserted": 0, "players_matched": 0,
            "draft_picks_inserted": 0, "draft_picks_skipped": 0,
            "matchups_inserted": 0, "matchups_skipped": 0,
            "bye_matchups_skipped": 0, "skipped_missing_owner_map": 0,
            "skipped_missing_player_map": 0,
        }

    monkeypatch.setattr(manage, "run_import_mfl_csv", fake_run)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "import-mfl-csv",
            "--target-league-id", "60",
            "--start-year", "2022",
            "--end-year", "2022",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured.get("source_mode") == "db"
    assert captured.get("input_root") is None
