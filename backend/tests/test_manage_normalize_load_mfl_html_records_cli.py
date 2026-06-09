from click.testing import CliRunner

import backend.manage as manage


def test_normalize_load_mfl_html_records_uses_temp_root_when_output_not_provided(monkeypatch, tmp_path):
    captured = {}

    def fake_run_normalize_mfl_html_records(**kwargs):
        captured["normalize"] = kwargs
        return {
            "input_root": kwargs["input_root"],
            "output_root": kwargs["output_root"],
            "files_processed": 2,
            "files_skipped": 0,
            "warnings": [],
            "rows_written_by_dataset": {},
        }

    def fake_run_load_mfl_html_normalized(**kwargs):
        captured["load"] = kwargs
        return {
            "run_id": 123,
            "input_roots": kwargs["input_roots"],
            "target_league_id": kwargs["target_league_id"],
            "files_seen": 2,
            "files_loaded": 2,
            "rows_seen": 10,
            "rows_inserted": 10,
            "rows_skipped_existing": 0,
            "warnings": [],
        }

    monkeypatch.setattr(manage, "run_normalize_mfl_html_records", fake_run_normalize_mfl_html_records)
    monkeypatch.setattr(manage, "run_load_mfl_html_normalized", fake_run_load_mfl_html_normalized)

    input_root = tmp_path / "html"
    input_root.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "normalize-load-mfl-html-records",
            "--input-root",
            str(input_root),
        ],
    )

    assert result.exit_code == 0
    assert "MFL HTML normalize+load summary" in result.output
    assert "Temporary normalized root used: True" in result.output

    normalized_root = captured["normalize"]["output_root"]
    assert normalized_root
    assert captured["load"]["input_roots"] == [normalized_root]
    assert captured["load"]["dry_run"] is True


def test_normalize_load_mfl_html_records_uses_explicit_output_root(monkeypatch, tmp_path):
    captured = {}

    def fake_run_normalize_mfl_html_records(**kwargs):
        captured["normalize"] = kwargs
        return {
            "input_root": kwargs["input_root"],
            "output_root": kwargs["output_root"],
            "files_processed": 1,
            "files_skipped": 0,
            "warnings": [],
            "rows_written_by_dataset": {},
        }

    def fake_run_load_mfl_html_normalized(**kwargs):
        captured["load"] = kwargs
        return {
            "run_id": 456,
            "input_roots": kwargs["input_roots"],
            "target_league_id": kwargs["target_league_id"],
            "files_seen": 1,
            "files_loaded": 1,
            "rows_seen": 5,
            "rows_inserted": 5,
            "rows_skipped_existing": 0,
            "warnings": [],
        }

    monkeypatch.setattr(manage, "run_normalize_mfl_html_records", fake_run_normalize_mfl_html_records)
    monkeypatch.setattr(manage, "run_load_mfl_html_normalized", fake_run_load_mfl_html_normalized)

    input_root = tmp_path / "html"
    output_root = tmp_path / "normalized"
    input_root.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "normalize-load-mfl-html-records",
            "--input-root",
            str(input_root),
            "--output-root",
            str(output_root),
            "--apply",
            "--target-league-id",
            "60",
        ],
    )

    assert result.exit_code == 0
    assert "Temporary normalized root used: False" in result.output
    assert captured["normalize"]["output_root"] == str(output_root)
    assert captured["load"]["input_roots"] == [str(output_root)]
    assert captured["load"]["dry_run"] is False
    assert captured["load"]["target_league_id"] == 60


def test_normalize_load_mfl_html_records_requires_apply_for_truncate(tmp_path):
    input_root = tmp_path / "html"
    input_root.mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "normalize-load-mfl-html-records",
            "--input-root",
            str(input_root),
            "--truncate-before-load",
        ],
    )

    assert result.exit_code != 0
    assert "--truncate-before-load requires --apply" in result.output
