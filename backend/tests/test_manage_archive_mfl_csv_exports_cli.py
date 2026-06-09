from click.testing import CliRunner

import backend.manage as manage


def test_archive_mfl_csv_exports_requires_legacy_ack_flag(tmp_path):
    input_root = tmp_path / "exports"
    input_root.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "archive-mfl-csv-exports",
            "--input-root",
            str(input_root),
        ],
    )

    assert result.exit_code != 0
    assert "--allow-legacy-csv-source is required for archive-mfl-csv-exports" in result.output


def test_archive_mfl_csv_exports_runs_with_legacy_ack_flag(monkeypatch, tmp_path):
    captured = {}

    def fake_run_archive_mfl_csv_exports(**kwargs):
        captured.update(kwargs)
        return {
            "run_id": "run-1",
            "input_root": kwargs["input_root"],
            "archive_path": "archive.zip",
            "manifest_path": "archive.manifest.json",
            "csv_files_seen": 2,
            "csv_files_archived": 2,
            "csv_files_pruned": 0,
            "bytes_seen": 1234,
            "warnings": [],
        }

    monkeypatch.setattr(manage, "run_archive_mfl_csv_exports", fake_run_archive_mfl_csv_exports)

    input_root = tmp_path / "exports"
    input_root.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "archive-mfl-csv-exports",
            "--input-root",
            str(input_root),
            "--allow-legacy-csv-source",
        ],
    )

    assert result.exit_code == 0
    assert "MFL CSV archive summary" in result.output
    assert captured["input_root"] == str(input_root)
    assert captured["dry_run"] is True
    assert captured["prune_csv"] is False
