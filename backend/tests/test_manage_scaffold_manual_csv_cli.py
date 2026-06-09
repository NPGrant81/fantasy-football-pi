from click.testing import CliRunner

import backend.manage as manage


def test_scaffold_mfl_manual_csv_requires_legacy_ack_flag():
    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "scaffold-mfl-manual-csv",
            "--start-year",
            "2002",
            "--end-year",
            "2003",
        ],
    )

    assert result.exit_code != 0
    assert "--allow-legacy-csv-source is required for scaffold-mfl-manual-csv" in result.output


def test_scaffold_mfl_manual_csv_runs_with_legacy_ack_flag(monkeypatch):
    captured = {}

    def fake_run_scaffold_mfl_manual_csv(**kwargs):
        captured.update(kwargs)
        return {
            "seasons": [2002, 2003],
            "report_types": ["franchises", "players", "draftResults"],
            "files_created": 6,
            "output_root": "exports/history_manual",
        }

    monkeypatch.setattr(manage, "run_scaffold_mfl_manual_csv", fake_run_scaffold_mfl_manual_csv)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "scaffold-mfl-manual-csv",
            "--start-year",
            "2002",
            "--end-year",
            "2003",
            "--allow-legacy-csv-source",
        ],
    )

    assert result.exit_code == 0
    assert "Manual CSV scaffold summary" in result.output
    assert captured["start_year"] == 2002
    assert captured["end_year"] == 2003
