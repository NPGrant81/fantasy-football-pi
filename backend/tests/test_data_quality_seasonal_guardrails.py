from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.models as models


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


def _completed_regular_weeks(matchups):
    return sorted(
        {
            int(matchup.week)
            for matchup in matchups
            if matchup.is_completed and not matchup.is_playoff and matchup.week is not None
        }
    )


def _missing_weeks(weeks):
    if not weeks:
        return []
    expected = set(range(min(weeks), max(weeks) + 1))
    return sorted(expected.difference(set(weeks)))


def _playoff_week_violations(matchups):
    regular_weeks = _completed_regular_weeks(matchups)
    if not regular_weeks:
        return []
    regular_end_week = max(regular_weeks)
    return [
        matchup.id
        for matchup in matchups
        if matchup.is_playoff and matchup.week is not None and int(matchup.week) <= regular_end_week
    ]


def _future_transaction_ids(transactions, *, now_utc, tolerance_minutes=5):
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    cutoff = now_utc + timedelta(minutes=tolerance_minutes)
    violations = []
    for txn in transactions:
        if txn.timestamp is None:
            continue
        txn_timestamp = txn.timestamp
        if txn_timestamp.tzinfo is None:
            txn_timestamp = txn_timestamp.replace(tzinfo=timezone.utc)
        if txn_timestamp > cutoff:
            violations.append(txn.id)
    return violations


def _ownership_chain_break_ids(transactions):
    by_player = {}
    for txn in sorted(transactions, key=lambda row: row.timestamp or datetime.min.replace(tzinfo=timezone.utc)):
        by_player.setdefault(txn.player_id, []).append(txn)

    broken = []
    for player_rows in by_player.values():
        previous_new_owner = None
        for txn in player_rows:
            if previous_new_owner is not None and txn.old_owner_id is not None:
                if txn.old_owner_id != previous_new_owner:
                    broken.append(txn.id)
            previous_new_owner = txn.new_owner_id
    return broken


def test_seasonal_week_coverage_guardrail_detects_gaps(db_session):
    league = models.League(name="Week Coverage League")
    owner_a = models.User(username="owner-a", email=None, hashed_password="h")
    owner_b = models.User(username="owner-b", email=None, hashed_password="h")
    db_session.add_all([league, owner_a, owner_b])
    db_session.commit()
    db_session.refresh(league)
    db_session.refresh(owner_a)
    db_session.refresh(owner_b)

    db_session.add_all(
        [
            models.Matchup(
                league_id=league.id,
                season=2026,
                week=1,
                home_team_id=owner_a.id,
                away_team_id=owner_b.id,
                home_score=100.0,
                away_score=95.0,
                is_completed=True,
                is_playoff=False,
            ),
            models.Matchup(
                league_id=league.id,
                season=2026,
                week=2,
                home_team_id=owner_b.id,
                away_team_id=owner_a.id,
                home_score=102.0,
                away_score=97.0,
                is_completed=True,
                is_playoff=False,
            ),
            # week=3 is intentionally missing
            models.Matchup(
                league_id=league.id,
                season=2026,
                week=4,
                home_team_id=owner_a.id,
                away_team_id=owner_b.id,
                home_score=108.0,
                away_score=99.0,
                is_completed=True,
                is_playoff=False,
            ),
        ]
    )
    db_session.commit()

    matchups = db_session.query(models.Matchup).filter(models.Matchup.league_id == league.id).all()
    weeks = _completed_regular_weeks(matchups)

    assert weeks == [1, 2, 4]
    assert _missing_weeks(weeks) == [3]


def test_playoff_boundary_guardrail_detects_early_playoff_week(db_session):
    league = models.League(name="Playoff Boundary League")
    owner_a = models.User(username="boundary-a", email=None, hashed_password="h")
    owner_b = models.User(username="boundary-b", email=None, hashed_password="h")
    db_session.add_all([league, owner_a, owner_b])
    db_session.commit()
    db_session.refresh(league)
    db_session.refresh(owner_a)
    db_session.refresh(owner_b)

    db_session.add_all(
        [
            models.Matchup(
                league_id=league.id,
                season=2026,
                week=1,
                home_team_id=owner_a.id,
                away_team_id=owner_b.id,
                home_score=100.0,
                away_score=90.0,
                is_completed=True,
                is_playoff=False,
            ),
            models.Matchup(
                league_id=league.id,
                season=2026,
                week=2,
                home_team_id=owner_b.id,
                away_team_id=owner_a.id,
                home_score=104.0,
                away_score=103.0,
                is_completed=True,
                is_playoff=False,
            ),
            models.Matchup(
                league_id=league.id,
                season=2026,
                week=2,
                home_team_id=owner_a.id,
                away_team_id=owner_b.id,
                home_score=111.0,
                away_score=100.0,
                is_completed=True,
                is_playoff=True,
            ),
        ]
    )
    db_session.commit()

    matchups = db_session.query(models.Matchup).filter(models.Matchup.league_id == league.id).all()
    violation_ids = _playoff_week_violations(matchups)

    assert len(violation_ids) == 1


def test_transaction_freshness_guardrail_detects_future_timestamps(db_session):
    now = datetime.now(timezone.utc)

    league = models.League(name="Txn Freshness League")
    old_owner = models.User(username="old-owner", email=None, hashed_password="h")
    new_owner = models.User(username="new-owner", email=None, hashed_password="h")
    player = models.Player(name="Future Txn Player", position="RB", nfl_team="DET")
    db_session.add_all([league, old_owner, new_owner, player])
    db_session.commit()
    db_session.refresh(league)
    db_session.refresh(old_owner)
    db_session.refresh(new_owner)
    db_session.refresh(player)

    db_session.add_all(
        [
            models.TransactionHistory(
                league_id=league.id,
                season=2026,
                player_id=player.id,
                old_owner_id=old_owner.id,
                new_owner_id=new_owner.id,
                transaction_type="trade",
                timestamp=now,
            ),
            models.TransactionHistory(
                league_id=league.id,
                season=2026,
                player_id=player.id,
                old_owner_id=new_owner.id,
                new_owner_id=old_owner.id,
                transaction_type="trade",
                timestamp=now + timedelta(minutes=15),
            ),
        ]
    )
    db_session.commit()

    transactions = db_session.query(models.TransactionHistory).filter(models.TransactionHistory.league_id == league.id).all()
    violations = _future_transaction_ids(transactions, now_utc=now, tolerance_minutes=5)

    assert len(violations) == 1


def test_ownership_chain_guardrail_detects_owner_transitions_out_of_order(db_session):
    base_time = datetime(2026, 3, 1, tzinfo=timezone.utc)

    league = models.League(name="Ownership Chain League")
    owner_a = models.User(username="owner-a", email=None, hashed_password="h")
    owner_b = models.User(username="owner-b", email=None, hashed_password="h")
    owner_c = models.User(username="owner-c", email=None, hashed_password="h")
    player = models.Player(name="Chain Player", position="WR", nfl_team="DAL")
    db_session.add_all([league, owner_a, owner_b, owner_c, player])
    db_session.commit()
    db_session.refresh(league)
    db_session.refresh(owner_a)
    db_session.refresh(owner_b)
    db_session.refresh(owner_c)
    db_session.refresh(player)

    db_session.add_all(
        [
            models.TransactionHistory(
                league_id=league.id,
                season=2026,
                player_id=player.id,
                old_owner_id=None,
                new_owner_id=owner_a.id,
                transaction_type="draft",
                timestamp=base_time,
            ),
            models.TransactionHistory(
                league_id=league.id,
                season=2026,
                player_id=player.id,
                old_owner_id=owner_a.id,
                new_owner_id=owner_b.id,
                transaction_type="trade",
                timestamp=base_time + timedelta(days=1),
            ),
            # broken chain: should old_owner_id be owner_b, not owner_c
            models.TransactionHistory(
                league_id=league.id,
                season=2026,
                player_id=player.id,
                old_owner_id=owner_c.id,
                new_owner_id=owner_a.id,
                transaction_type="trade",
                timestamp=base_time + timedelta(days=2),
            ),
        ]
    )
    db_session.commit()

    transactions = db_session.query(models.TransactionHistory).filter(models.TransactionHistory.league_id == league.id).all()
    broken_ids = _ownership_chain_break_ids(transactions)

    assert len(broken_ids) == 1
