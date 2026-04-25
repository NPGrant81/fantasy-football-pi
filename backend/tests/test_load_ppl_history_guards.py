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


def test_main_refuses_without_env_flag(monkeypatch):
    """main() must exit(1) when FFPI_ALLOW_LEGACY_CSV_BOOTSTRAP is not set."""
    monkeypatch.delenv(load_ppl_history.CSV_BOOTSTRAP_ENV_FLAG, raising=False)
    import pytest
    with pytest.raises(SystemExit) as exc_info:
        load_ppl_history.main(argv=[])
    assert exc_info.value.code == 1


def test_main_refuses_with_env_but_no_cli_flag(monkeypatch):
    """main() must exit(1) when env is set but CLI flag is omitted."""
    monkeypatch.setenv(load_ppl_history.CSV_BOOTSTRAP_ENV_FLAG, "1")
    import pytest
    with pytest.raises(SystemExit) as exc_info:
        load_ppl_history.main(argv=[])
    assert exc_info.value.code == 1


def test_main_refuses_when_csv_sources_missing(monkeypatch, tmp_path):
    """main() must exit(1) even with both flags if CSV source files are absent."""
    monkeypatch.setenv(load_ppl_history.CSV_BOOTSTRAP_ENV_FLAG, "1")
    monkeypatch.setattr(load_ppl_history, "DATA_DIR", str(tmp_path))
    import pytest
    with pytest.raises(SystemExit) as exc_info:
        load_ppl_history.main(argv=["--allow-legacy-csv-bootstrap"])
    assert exc_info.value.code == 1
