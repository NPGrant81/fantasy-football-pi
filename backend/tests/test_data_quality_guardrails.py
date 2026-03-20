from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.models as models
from backend.routers.league import get_league_owners
from backend.scripts import extract_mfl_history, load_mfl_html_normalized


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


def test_extract_players_schema_guardrail_has_required_columns():
    payload = {
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

    rows = extract_mfl_history._normalize_players(
        payload,
        season=2002,
        league_id="29721",
        extracted_at="2026-03-19T00:00:00+00:00",
    )

    assert len(rows) == 1
    required_columns = {
        "season",
        "league_id",
        "source_system",
        "source_endpoint",
        "extracted_at_utc",
        "player_mfl_id",
        "player_name",
        "position",
        "nfl_team",
        "status",
        "raw_player",
    }
    assert required_columns.issubset(set(rows[0].keys()))


def test_extract_players_completeness_guardrail_for_core_fields():
    payload = {
        "players": {
            "player": [
                {"id": "1001", "name": "Player One", "position": "QB", "team": "BUF", "status": "A"},
                {"id": "1002", "name": "Player Two", "position": "RB", "team": "KC", "status": "A"},
                {"id": "1003", "name": "Player Three", "position": "WR", "team": "SF", "status": "A"},
                # one intentionally sparse row to verify the threshold logic itself
                {"id": "", "name": "", "position": "TE", "team": "NE", "status": "A"},
            ]
        }
    }

    rows = extract_mfl_history._normalize_players(
        payload,
        season=2002,
        league_id="29721",
        extracted_at="2026-03-19T00:00:00+00:00",
    )

    def completeness_ratio(field_name: str) -> float:
        non_empty = sum(1 for row in rows if str(row.get(field_name) or "").strip())
        return non_empty / len(rows)

    # Guardrail thresholds for critical player identity fields.
    assert completeness_ratio("player_mfl_id") >= 0.75
    assert completeness_ratio("player_name") >= 0.75
    assert completeness_ratio("position") >= 0.95


def test_extract_players_freshness_guardrail_extracted_at_not_future():
    now = datetime.now(timezone.utc)
    extracted_at = now.isoformat()
    rows = extract_mfl_history._normalize_players(
        {"players": {"player": [{"id": "1001", "name": "Player One", "position": "QB", "team": "BUF"}]}},
        season=2026,
        league_id="11422",
        extracted_at=extracted_at,
    )

    parsed = datetime.fromisoformat(str(rows[0]["extracted_at_utc"]).replace("Z", "+00:00"))
    assert parsed <= now + timedelta(minutes=1)


def test_standings_reconcile_with_completed_matchups(db_session):
    league = models.League(name="Reconcile League")
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    owner_a = models.User(username="owner-a", email=None, hashed_password="h", league_id=league.id)
    owner_b = models.User(username="owner-b", email=None, hashed_password="h", league_id=league.id)
    owner_c = models.User(username="owner-c", email=None, hashed_password="h", league_id=league.id)
    db_session.add_all([owner_a, owner_b, owner_c])
    db_session.commit()
    db_session.refresh(owner_a)
    db_session.refresh(owner_b)
    db_session.refresh(owner_c)

    # Completed matchups should be the only records reflected in standings.
    db_session.add_all(
        [
            models.Matchup(
                week=1,
                home_team_id=owner_a.id,
                away_team_id=owner_b.id,
                home_score=120.0,
                away_score=100.0,
                is_completed=True,
                league_id=league.id,
            ),
            models.Matchup(
                week=2,
                home_team_id=owner_b.id,
                away_team_id=owner_c.id,
                home_score=98.0,
                away_score=98.0,
                is_completed=True,
                league_id=league.id,
            ),
            models.Matchup(
                week=3,
                home_team_id=owner_c.id,
                away_team_id=owner_a.id,
                home_score=90.0,
                away_score=110.0,
                is_completed=False,
                league_id=league.id,
            ),
        ]
    )
    db_session.commit()

    owners = get_league_owners(league_id=league.id, db=db_session)

    total_pf = sum(float(owner["pf"]) for owner in owners)
    total_pa = sum(float(owner["pa"]) for owner in owners)
    total_wins = sum(int(owner["wins"]) for owner in owners)
    total_losses = sum(int(owner["losses"]) for owner in owners)

    completed_matchups = (
        db_session.query(models.Matchup)
        .filter(models.Matchup.league_id == league.id, models.Matchup.is_completed.is_(True))
        .all()
    )
    expected_points = sum(float((matchup.home_score or 0) + (matchup.away_score or 0)) for matchup in completed_matchups)

    # Data-quality reconciliation invariants.
    assert total_pf == pytest.approx(expected_points)
    assert total_pa == pytest.approx(expected_points)
    assert total_wins == total_losses


def test_transaction_history_referential_guardrail_detects_cross_league_owner(db_session):
    league_a = models.League(name="League A")
    league_b = models.League(name="League B")
    db_session.add_all([league_a, league_b])
    db_session.commit()
    db_session.refresh(league_a)
    db_session.refresh(league_b)

    owner_a = models.User(username="owner-a", email=None, hashed_password="h", league_id=league_a.id)
    outsider = models.User(username="outsider", email=None, hashed_password="h", league_id=league_b.id)
    player = models.Player(name="Cross League Player", position="WR", nfl_team="BUF")
    db_session.add_all([owner_a, outsider, player])
    db_session.commit()
    db_session.refresh(owner_a)
    db_session.refresh(outsider)
    db_session.refresh(player)

    # Intentional anomaly: transaction in league_a references new_owner from league_b.
    db_session.add(
        models.TransactionHistory(
            league_id=league_a.id,
            season=2026,
            player_id=player.id,
            old_owner_id=owner_a.id,
            new_owner_id=outsider.id,
            transaction_type="trade",
        )
    )
    db_session.commit()

    transactions = db_session.query(models.TransactionHistory).all()
    cross_league_refs = []
    for txn in transactions:
        if txn.new_owner_id is None:
            continue
        if txn.new_owner is None:
            cross_league_refs.append(txn.id)
            continue
        if txn.new_owner.league_id != txn.league_id:
            cross_league_refs.append(txn.id)

    assert len(cross_league_refs) == 1


class _FakeFilterQuery:
    def __init__(self, parent):
        self.parent = parent
        self._dataset_key = None
        self._fingerprint = None

    def filter(self, expression):
        left = getattr(expression, "left", None)
        right = getattr(expression, "right", None)
        key = getattr(left, "key", None)
        value = getattr(right, "value", None)

        if key == "dataset_key":
            self._dataset_key = value
        if key == "row_fingerprint":
            self._fingerprint = value
        return self

    def first(self):
        if (self._dataset_key, self._fingerprint) in self.parent.existing_fact_rows:
            return (1,)
        return None


class _FakeDeleteQuery:
    def delete(self, synchronize_session=False):
        return 0


class _FakeDb:
    def __init__(self):
        self.added = []
        self.closed = False
        self.existing_fact_rows = set()
        self._next_id = 1

    def query(self, model_or_column):
        key = getattr(model_or_column, "key", None)
        if key == "id":
            return _FakeFilterQuery(self)
        return _FakeDeleteQuery()

    def add(self, record):
        self.added.append(record)
        if hasattr(record, "row_fingerprint") and hasattr(record, "dataset_key"):
            self.existing_fact_rows.add((record.dataset_key, record.row_fingerprint))

    def commit(self):
        return None

    def rollback(self):
        return None

    def refresh(self, record):
        if getattr(record, "id", None) is None:
            record.id = self._next_id
            self._next_id += 1

    def flush(self):
        return None

    def close(self):
        self.closed = True


def test_load_normalized_html_is_idempotent_for_existing_rows(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "html_league_awards_normalized"
    dataset_dir.mkdir(parents=True)

    csv_path = dataset_dir / "2026.csv"
    pd.DataFrame(
        [
            {
                "season": 2026,
                "league_id": "11422",
                "source_endpoint": "league_awards",
                "source_url": "https://example.test/awards",
                "extracted_at_utc": "2026-03-19T00:00:00Z",
                "normalization_version": "v1",
                "award_type": "MVP",
            }
        ]
    ).to_csv(csv_path, index=False)

    fake_db = _FakeDb()
    monkeypatch.setattr(load_mfl_html_normalized, "SessionLocal", lambda: fake_db)

    first = load_mfl_html_normalized.run_load_mfl_html_normalized(
        input_roots=[str(tmp_path)],
        dry_run=False,
        target_league_id=1,
    )
    second = load_mfl_html_normalized.run_load_mfl_html_normalized(
        input_roots=[str(tmp_path)],
        dry_run=False,
        target_league_id=1,
    )

    assert first["rows_inserted"] == 1
    assert first["rows_skipped_existing"] == 0
    assert second["rows_inserted"] == 0
    assert second["rows_skipped_existing"] == 1


def test_load_normalized_html_inserts_when_row_payload_changes(tmp_path, monkeypatch):
    dataset_dir = tmp_path / "html_league_awards_normalized"
    dataset_dir.mkdir(parents=True)

    csv_path = dataset_dir / "2026.csv"
    pd.DataFrame(
        [
            {
                "season": 2026,
                "league_id": "11422",
                "source_endpoint": "league_awards",
                "source_url": "https://example.test/awards",
                "extracted_at_utc": "2026-03-19T00:00:00Z",
                "normalization_version": "v1",
                "award_type": "MVP",
            }
        ]
    ).to_csv(csv_path, index=False)

    fake_db = _FakeDb()
    monkeypatch.setattr(load_mfl_html_normalized, "SessionLocal", lambda: fake_db)

    first = load_mfl_html_normalized.run_load_mfl_html_normalized(
        input_roots=[str(tmp_path)],
        dry_run=False,
        target_league_id=1,
    )

    # Change one value to force a new fingerprint.
    pd.DataFrame(
        [
            {
                "season": 2026,
                "league_id": "11422",
                "source_endpoint": "league_awards",
                "source_url": "https://example.test/awards",
                "extracted_at_utc": "2026-03-19T00:00:00Z",
                "normalization_version": "v1",
                "award_type": "OPoY",
            }
        ]
    ).to_csv(csv_path, index=False)

    second = load_mfl_html_normalized.run_load_mfl_html_normalized(
        input_roots=[str(tmp_path)],
        dry_run=False,
        target_league_id=1,
    )

    assert first["rows_inserted"] == 1
    assert second["rows_inserted"] == 1
    assert second["rows_skipped_existing"] == 0
