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


def test_import_mfl_csv_supports_db_source_mode(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        league = models.League(name="Legacy League DB")
        session.add(league)
        session.flush()

        session.add_all(
            [
                models.User(
                    username="alpha-owner",
                    email="alpha@example.com",
                    hashed_password="x",
                    league_id=league.id,
                    team_name="Alpha Team",
                ),
                models.User(
                    username="beta-owner",
                    email="beta@example.com",
                    hashed_password="x",
                    league_id=league.id,
                    team_name="Beta Team",
                ),
                models.Player(
                    name="Player One",
                    position="QB",
                    nfl_team="BUF",
                    adp=1.0,
                    projected_points=10.0,
                ),
            ]
        )

        season = 2023
        league_id = "11422"
        facts = [
            {
                "dataset_key": "html_franchises_normalized",
                "record_json": {
                    "season": str(season),
                    "league_id": league_id,
                    "franchise_id": "A",
                    "franchise_name": "Alpha Team",
                    "owner_name": "alpha-owner",
                },
            },
            {
                "dataset_key": "html_franchises_normalized",
                "record_json": {
                    "season": str(season),
                    "league_id": league_id,
                    "franchise_id": "B",
                    "franchise_name": "Beta Team",
                    "owner_name": "beta-owner",
                },
            },
            {
                "dataset_key": "html_players_normalized",
                "record_json": {
                    "season": str(season),
                    "league_id": league_id,
                    "player_mfl_id": "1001",
                    "player_name": "Player One",
                    "position": "QB",
                    "nfl_team": "BUF",
                },
            },
            {
                "dataset_key": "html_players_normalized",
                "record_json": {
                    "season": str(season),
                    "league_id": league_id,
                    "player_mfl_id": "1002",
                    "player_name": "Player Two",
                    "position": "WR",
                    "nfl_team": "KC",
                },
            },
            {
                "dataset_key": "html_draft_results_normalized",
                "record_json": {
                    "season": str(season),
                    "league_id": league_id,
                    "franchise_id": "A",
                    "player_mfl_id": "1001",
                    "round": "1",
                    "pick_number": "1",
                    "winning_bid": "$25",
                },
            },
            {
                "dataset_key": "html_draft_results_normalized",
                "record_json": {
                    "season": str(season),
                    "league_id": league_id,
                    "franchise_id": "B",
                    "player_mfl_id": "1002",
                    "round": "1",
                    "pick_number": "2",
                    "winning_bid": "$18",
                },
            },
            {
                "dataset_key": "html_schedule_normalized",
                "record_json": {
                    "season": str(season),
                    "league_id": league_id,
                    "week": "1",
                    "home_franchise_id": "A",
                    "away_franchise_id": "B",
                    "home_score": "101.5",
                    "away_score": "98.0",
                },
            },
            {
                "dataset_key": "html_transactions_normalized",
                "record_json": {
                    "season": str(season),
                    "league_id": league_id,
                    "week": "1",
                    "franchise_id": "A",
                    "player_mfl_id": "1002",
                    "transaction_type": "waiver_add",
                },
            },
        ]
        for idx, payload in enumerate(facts, start=1):
            session.add(
                models.MflHtmlRecordFact(
                    dataset_key=payload["dataset_key"],
                    season=season,
                    league_id=league_id,
                    normalization_version="v1",
                    row_fingerprint=f"fp-{idx}",
                    record_json=payload["record_json"],
                )
            )

        session.commit()
    finally:
        session.close()

    monkeypatch.setattr(import_mfl_csv, "SessionLocal", TestingSessionLocal)

    summary = import_mfl_csv.run_import_mfl_csv(
        input_root=None,
        target_league_id=1,
        start_year=season,
        end_year=season,
        dry_run=False,
        source_mode="db",
        source_league_id=league_id,
    )

    assert summary["players_matched"] == 1
    assert summary["players_inserted"] == 1
    assert summary["draft_picks_inserted"] == 2
    assert summary["draft_picks_skipped"] == 0
    assert summary["matchups_inserted"] == 1
    assert summary["transactions_inserted"] == 1


def test_import_mfl_csv_db_mode_filters_by_source_league_and_season(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        league = models.League(name="Legacy League DB Filter")
        session.add(league)
        session.flush()

        session.add_all(
            [
                models.User(
                    username="alpha-owner",
                    email="alpha@example.com",
                    hashed_password="x",
                    league_id=league.id,
                    team_name="Alpha Team",
                ),
                models.User(
                    username="beta-owner",
                    email="beta@example.com",
                    hashed_password="x",
                    league_id=league.id,
                    team_name="Beta Team",
                ),
                models.Player(
                    name="Player One",
                    position="QB",
                    nfl_team="BUF",
                    adp=1.0,
                    projected_points=10.0,
                ),
                models.Player(
                    name="Player Two",
                    position="WR",
                    nfl_team="KC",
                    adp=2.0,
                    projected_points=11.0,
                ),
            ]
        )

        target_league_id = "11422"
        other_league_id = "99999"
        season_a = 2022
        season_b = 2023

        facts = [
            # Target league seasons (should be imported)
            {
                "dataset_key": "html_franchises_normalized",
                "season": season_a,
                "league_id": target_league_id,
                "record_json": {
                    "season": str(season_a),
                    "league_id": target_league_id,
                    "franchise_id": "A",
                    "franchise_name": "Alpha Team",
                    "owner_name": "alpha-owner",
                },
            },
            {
                "dataset_key": "html_franchises_normalized",
                "season": season_a,
                "league_id": target_league_id,
                "record_json": {
                    "season": str(season_a),
                    "league_id": target_league_id,
                    "franchise_id": "B",
                    "franchise_name": "Beta Team",
                    "owner_name": "beta-owner",
                },
            },
            {
                "dataset_key": "html_franchises_normalized",
                "season": season_b,
                "league_id": target_league_id,
                "record_json": {
                    "season": str(season_b),
                    "league_id": target_league_id,
                    "franchise_id": "A",
                    "franchise_name": "Alpha Team",
                    "owner_name": "alpha-owner",
                },
            },
            {
                "dataset_key": "html_franchises_normalized",
                "season": season_b,
                "league_id": target_league_id,
                "record_json": {
                    "season": str(season_b),
                    "league_id": target_league_id,
                    "franchise_id": "B",
                    "franchise_name": "Beta Team",
                    "owner_name": "beta-owner",
                },
            },
            {
                "dataset_key": "html_players_normalized",
                "season": season_a,
                "league_id": target_league_id,
                "record_json": {
                    "season": str(season_a),
                    "league_id": target_league_id,
                    "player_mfl_id": "1001",
                    "player_name": "Player One",
                    "position": "QB",
                    "nfl_team": "BUF",
                },
            },
            {
                "dataset_key": "html_players_normalized",
                "season": season_b,
                "league_id": target_league_id,
                "record_json": {
                    "season": str(season_b),
                    "league_id": target_league_id,
                    "player_mfl_id": "1002",
                    "player_name": "Player Two",
                    "position": "WR",
                    "nfl_team": "KC",
                },
            },
            {
                "dataset_key": "html_draft_results_normalized",
                "season": season_a,
                "league_id": target_league_id,
                "record_json": {
                    "season": str(season_a),
                    "league_id": target_league_id,
                    "franchise_id": "A",
                    "player_mfl_id": "1001",
                    "round": "1",
                    "pick_number": "1",
                    "winning_bid": "$20",
                },
            },
            {
                "dataset_key": "html_draft_results_normalized",
                "season": season_b,
                "league_id": target_league_id,
                "record_json": {
                    "season": str(season_b),
                    "league_id": target_league_id,
                    "franchise_id": "B",
                    "player_mfl_id": "1002",
                    "round": "1",
                    "pick_number": "2",
                    "winning_bid": "$18",
                },
            },
            # Non-target source league (should be ignored by source_league_id filter)
            {
                "dataset_key": "html_draft_results_normalized",
                "season": season_b,
                "league_id": other_league_id,
                "record_json": {
                    "season": str(season_b),
                    "league_id": other_league_id,
                    "franchise_id": "A",
                    "player_mfl_id": "1001",
                    "round": "2",
                    "pick_number": "9",
                    "winning_bid": "$5",
                },
            },
            # Out-of-range season (should be ignored by season filter)
            {
                "dataset_key": "html_draft_results_normalized",
                "season": 2024,
                "league_id": target_league_id,
                "record_json": {
                    "season": "2024",
                    "league_id": target_league_id,
                    "franchise_id": "A",
                    "player_mfl_id": "1001",
                    "round": "3",
                    "pick_number": "20",
                    "winning_bid": "$3",
                },
            },
        ]

        for idx, payload in enumerate(facts, start=1):
            session.add(
                models.MflHtmlRecordFact(
                    dataset_key=payload["dataset_key"],
                    season=payload["season"],
                    league_id=payload["league_id"],
                    normalization_version="v1",
                    row_fingerprint=f"filter-fp-{idx}",
                    record_json=payload["record_json"],
                )
            )

        session.commit()
    finally:
        session.close()

    monkeypatch.setattr(import_mfl_csv, "SessionLocal", TestingSessionLocal)

    summary = import_mfl_csv.run_import_mfl_csv(
        input_root=None,
        target_league_id=1,
        start_year=season_a,
        end_year=season_b,
        dry_run=False,
        source_mode="db",
        source_league_id=target_league_id,
    )

    assert summary["draft_picks_inserted"] == 2
    assert summary["draft_picks_skipped"] == 0

    verify_session = TestingSessionLocal()
    try:
        picks = (
            verify_session.query(models.DraftPick)
            .filter(models.DraftPick.league_id == 1)
            .order_by(models.DraftPick.year.asc(), models.DraftPick.pick_num.asc())
            .all()
        )
        assert len(picks) == 2
        assert sorted(int(p.year) for p in picks) == [season_a, season_b]
    finally:
        verify_session.close()