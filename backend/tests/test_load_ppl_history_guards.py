import os

from backend.scripts import load_ppl_history


def test_legacy_csv_bootstrap_opted_in_requires_env_and_cli(monkeypatch):
    monkeypatch.delenv(load_ppl_history.CSV_BOOTSTRAP_ENV_FLAG, raising=False)
    assert load_ppl_history.legacy_csv_bootstrap_opted_in(cli_flag_enabled=False) is False
    assert load_ppl_history.legacy_csv_bootstrap_opted_in(cli_flag_enabled=True) is False

    monkeypatch.setenv(load_ppl_history.CSV_BOOTSTRAP_ENV_FLAG, "1")
    assert load_ppl_history.legacy_csv_bootstrap_opted_in(cli_flag_enabled=False) is False
    assert load_ppl_history.legacy_csv_bootstrap_opted_in(cli_flag_enabled=True) is True


def test_validate_required_csv_sources_reports_missing_files(tmp_path):
    missing = load_ppl_history.validate_required_csv_sources(str(tmp_path))
    assert len(missing) == 4

    for name in ["users.csv", "players.csv", "positions.csv", "draft_results.csv"]:
        (tmp_path / name).write_text("header\n", encoding="utf-8")

    assert load_ppl_history.validate_required_csv_sources(str(tmp_path)) == []
