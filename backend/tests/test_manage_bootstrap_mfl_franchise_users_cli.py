from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.manage as manage
from backend import models


def _build_test_sessionlocal():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


def test_bootstrap_mfl_franchise_users_auto_selects_latest_db_season(monkeypatch):
    TestingSessionLocal = _build_test_sessionlocal()

    db = TestingSessionLocal()
    try:
        db.add_all(
            [
                models.MflHtmlRecordFact(
                    dataset_key="html_franchises_normalized",
                    season=2023,
                    league_id="11422",
                    normalization_version="v1",
                    row_fingerprint="bootstrap-2023",
                    record_json={
                        "season": "2023",
                        "league_id": "11422",
                        "franchise_id": "0001",
                        "franchise_name": "Older Team",
                    },
                ),
                models.MflHtmlRecordFact(
                    dataset_key="html_franchises_normalized",
                    season=2024,
                    league_id="11422",
                    normalization_version="v1",
                    row_fingerprint="bootstrap-2024",
                    record_json={
                        "season": "2024",
                        "league_id": "11422",
                        "franchise_id": "0002",
                        "franchise_name": "Latest Team",
                    },
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(manage, "SessionLocal", TestingSessionLocal)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "bootstrap-mfl-franchise-users",
            "--target-league-id",
            "60",
        ],
    )

    assert result.exit_code == 0
    assert "Bootstrap MFL franchise users" in result.output
    assert "Source: db:season=2024 (auto-latest)" in result.output
    assert "Users to create: 1" in result.output
    assert "[2024:0002] Latest Team" in result.output


def test_bootstrap_mfl_franchise_users_auto_select_respects_source_league(monkeypatch):
    TestingSessionLocal = _build_test_sessionlocal()

    db = TestingSessionLocal()
    try:
        db.add_all(
            [
                models.MflHtmlRecordFact(
                    dataset_key="html_franchises_normalized",
                    season=2026,
                    league_id="OTHER",
                    normalization_version="v1",
                    row_fingerprint="bootstrap-other-2026",
                    record_json={
                        "season": "2026",
                        "league_id": "OTHER",
                        "franchise_id": "0900",
                        "franchise_name": "Other League Team",
                    },
                ),
                models.MflHtmlRecordFact(
                    dataset_key="html_franchises_normalized",
                    season=2025,
                    league_id="11422",
                    normalization_version="v1",
                    row_fingerprint="bootstrap-11422-2025",
                    record_json={
                        "season": "2025",
                        "league_id": "11422",
                        "franchise_id": "0005",
                        "franchise_name": "Filtered Team",
                    },
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(manage, "SessionLocal", TestingSessionLocal)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "bootstrap-mfl-franchise-users",
            "--source-league-id",
            "11422",
            "--target-league-id",
            "60",
        ],
    )

    assert result.exit_code == 0
    assert "Source: db:season=2025,league_id=11422 (auto-latest)" in result.output
    assert "Users to create: 1" in result.output
    assert "[2025:0005] Filtered Team" in result.output


def test_bootstrap_mfl_franchise_users_errors_when_no_db_rows(monkeypatch):
    TestingSessionLocal = _build_test_sessionlocal()
    monkeypatch.setattr(manage, "SessionLocal", TestingSessionLocal)

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
    assert "No DB franchise rows found to bootstrap" in result.output


def test_bootstrap_mfl_franchise_users_rejects_removed_franchises_csv_option(tmp_path):
    csv_path = tmp_path / "franchises.csv"
    csv_path.write_text(
        "season,league_id,franchise_id,franchise_name,owner_name\n"
        "2003,11422,0006,Legacy CSV Team,Owner A\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "bootstrap-mfl-franchise-users",
            "--franchises-csv",
            str(csv_path),
            "--target-league-id",
            "60",
        ],
    )

    assert result.exit_code != 0
    assert "No such option: --franchises-csv" in result.output


def test_bootstrap_mfl_franchise_users_requires_db_facts_for_selected_season(monkeypatch):
    TestingSessionLocal = _build_test_sessionlocal()
    monkeypatch.setattr(manage, "SessionLocal", TestingSessionLocal)

    runner = CliRunner()
    result = runner.invoke(
        manage.cli,
        [
            "bootstrap-mfl-franchise-users",
            "--source-season",
            "2003",
            "--target-league-id",
            "60",
        ],
    )

    assert result.exit_code != 0
    assert "No franchise rows found for the selected DB source" in result.output
