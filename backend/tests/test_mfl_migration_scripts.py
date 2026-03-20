import csv
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models
from backend.scripts import extract_mfl_history, import_mfl_csv, reconcile_mfl_import, scaffold_mfl_manual_csv


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_run_mfl_history_extract_writes_raw_and_normalized_files(tmp_path, monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "players": {
                    "player": [
                        {
                            "id": "1001",
                            "name": "Player One",
                            "position": "QB",
                            "team": "BUF",
                            "status": "A",
                        }
                    ]
                }
            }

    calls = []

    def fake_get(self, url, params, headers, timeout):
        calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(extract_mfl_history.requests.Session, "get", fake_get)

    summary = extract_mfl_history.run_mfl_history_extract(
        start_year=2023,
        end_year=2023,
        report_types=["players"],
        output_root=str(tmp_path),
        timeout_seconds=9,
        session_cookie="MFL_AUTH=1",
    )

    assert summary["extracted_reports"] == 1
    assert summary["failed_reports"] == 0
    assert len(calls) == 1
    assert calls[0]["params"]["TYPE"] == "players"
    assert calls[0]["params"]["L"] == "11422"
    assert calls[0]["headers"]["Cookie"] == "MFL_AUTH=1"

    csv_path = tmp_path / "players" / "2023.csv"
    raw_path = tmp_path / "raw" / "players" / "2023.json"
    summary_path = tmp_path / "_run_summary.json"

    assert csv_path.exists()
    assert raw_path.exists()
    assert summary_path.exists()

    csv_rows = list(csv.DictReader(csv_path.open("r", encoding="utf-8", newline="")))
    assert len(csv_rows) == 1
    assert csv_rows[0]["player_mfl_id"] == "1001"
    assert csv_rows[0]["player_name"] == "Player One"

    raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
    assert raw_payload["players"]["player"][0]["team"] == "BUF"


def test_import_and_reconcile_mfl_csv_round_trip(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        league = models.League(name="Legacy League")
        session.add(league)
        session.flush()

        user_one = models.User(
            username="alpha-owner",
            email="alpha@example.com",
            hashed_password="x",
            league_id=league.id,
            team_name="Alpha Team",
        )
        user_two = models.User(
            username="beta-owner",
            email="beta@example.com",
            hashed_password="x",
            league_id=league.id,
            team_name="Beta Team",
        )
        existing_player = models.Player(
            name="Player One",
            position="QB",
            nfl_team="BUF",
            adp=1.0,
            projected_points=10.0,
        )
        session.add_all([user_one, user_two, existing_player])
        session.commit()
    finally:
        session.close()

    monkeypatch.setattr(import_mfl_csv, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(reconcile_mfl_import, "SessionLocal", TestingSessionLocal)

    season = 2023
    _write_csv(
        tmp_path / "franchises" / f"{season}.csv",
        [
            {
                "season": str(season),
                "league_id": "11422",
                "franchise_id": "A",
                "franchise_name": "Alpha Team",
                "owner_name": "alpha-owner",
            },
            {
                "season": str(season),
                "league_id": "11422",
                "franchise_id": "B",
                "franchise_name": "Beta Team",
                "owner_name": "beta-owner",
            },
        ],
    )
    _write_csv(
        tmp_path / "players" / f"{season}.csv",
        [
            {
                "season": str(season),
                "league_id": "11422",
                "player_mfl_id": "1001",
                "player_name": "Player One",
                "position": "QB",
                "nfl_team": "BUF",
            },
            {
                "season": str(season),
                "league_id": "11422",
                "player_mfl_id": "1002",
                "player_name": "Player Two",
                "position": "WR",
                "nfl_team": "KC",
            },
        ],
    )
    _write_csv(
        tmp_path / "draftResults" / f"{season}.csv",
        [
            {
                "season": str(season),
                "league_id": "11422",
                "franchise_id": "A",
                "player_mfl_id": "1001",
                "round": "1",
                "pick_number": "1",
                "winning_bid": "$25",
            },
            {
                "season": str(season),
                "league_id": "11422",
                "franchise_id": "B",
                "player_mfl_id": "1002",
                "round": "1",
                "pick_number": "2",
                "winning_bid": "$18",
            },
        ],
    )

    import_summary = import_mfl_csv.run_import_mfl_csv(
        input_root=str(tmp_path),
        target_league_id=1,
        start_year=season,
        end_year=season,
        dry_run=False,
    )

    assert import_summary["files_checked"] == 3
    assert import_summary["rows_invalid"] == 0
    assert import_summary["players_matched"] == 1
    assert import_summary["players_inserted"] == 1
    assert import_summary["draft_picks_inserted"] == 2
    assert import_summary["draft_picks_skipped"] == 0

    reconcile_output = tmp_path / "reconcile.json"
    reconcile_summary = reconcile_mfl_import.run_reconcile_mfl_import(
        input_root=str(tmp_path),
        target_league_id=1,
        start_year=season,
        end_year=season,
        output_json=str(reconcile_output),
    )

    assert reconcile_summary["mismatch_count"] == 0
    assert reconcile_summary["season_reports"][0]["checks"] == {
        "draft_results_vs_draft_picks": True,
        "franchises_vs_distinct_owners": True,
        "players_vs_distinct_players": True,
    }
    assert reconcile_output.exists()

    persisted_summary = json.loads(reconcile_output.read_text(encoding="utf-8"))
    assert persisted_summary["mismatch_count"] == 0


def test_run_scaffold_mfl_manual_csv_creates_header_only_templates(tmp_path):
    summary = scaffold_mfl_manual_csv.run_scaffold_mfl_manual_csv(
        start_year=2002,
        end_year=2003,
        output_root=str(tmp_path),
    )

    assert summary["files_created"] == 6
    assert summary["seasons"] == [2002, 2003]

    players_path = tmp_path / "players" / "2002.csv"
    draft_path = tmp_path / "draftResults" / "2003.csv"
    assert players_path.exists()
    assert draft_path.exists()

    player_headers = next(csv.reader(players_path.open("r", encoding="utf-8", newline="")))
    draft_headers = next(csv.reader(draft_path.open("r", encoding="utf-8", newline="")))
    assert player_headers[:5] == [
        "season",
        "league_id",
        "source_system",
        "source_endpoint",
        "extracted_at_utc",
    ]
    assert draft_headers[-2:] == ["winning_bid", "is_keeper_pick"]