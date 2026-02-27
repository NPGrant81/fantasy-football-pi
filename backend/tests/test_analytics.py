import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.analytics import get_efficiency_leaderboard, get_weekly_stats


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    # create the leaderboard view manually since alembic migrations do not run
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text(
            """
            CREATE VIEW league_efficiency_leaderboard AS
            SELECT 
                manager_id,
                league_id,
                COUNT(week) as weeks_played,
                SUM(actual_points_total) as total_actual,
                SUM(optimal_points_total) as total_optimal,
                ROUND(AVG(actual_points_total / NULLIF(optimal_points_total, 0)), 4) as avg_efficiency,
                SUM(points_left_on_bench) as total_points_lost
            FROM manager_efficiency
            GROUP BY manager_id, league_id
            ORDER BY avg_efficiency DESC;
            """
        ))
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_efficiency(db, league_id, manager_id, season, week, actual, optimal):
    rec = models.ManagerEfficiency(
        league_id=league_id,
        manager_id=manager_id,
        season=season,
        week=week,
        actual_points_total=actual,
        optimal_points_total=optimal,
        points_left_on_bench=optimal - actual,
        efficiency_rating=(actual / optimal if optimal else 0),
    )
    db.add(rec)
    db.commit()
    return rec


def test_leaderboard_and_weekly(db_session):
    # setup data for two managers
    make_efficiency(db_session, league_id=10, manager_id=1, season=2026, week=1, actual=100, optimal=120)
    make_efficiency(db_session, league_id=10, manager_id=1, season=2026, week=2, actual=80, optimal=100)
    make_efficiency(db_session, league_id=10, manager_id=2, season=2026, week=1, actual=90, optimal=100)

    # query leaderboard (should order manager1 first because avg efficiency 0.833 vs 0.9? wait compute: m1=(100/120+80/100)/2=0.833
    # m2=0.9 -> m2 should appear first
    lb = get_efficiency_leaderboard(league_id=10, season=2026, db=db_session)
    assert isinstance(lb, list)
    assert lb[0]["manager_id"] == 2
    assert lb[1]["manager_id"] == 1
    assert "efficiency_display" in lb[0]
    # ensure JSON data is not returned by leaderboard (should be removed)
    assert "optimal_lineup_json" not in lb[0]

    # weekly stats for manager 1
    weeks = get_weekly_stats(league_id=10, manager_id=1, season=2026, db=db_session)
    # the table contains no JSON yet, but weekly stats returns max/actual
    assert len(weeks) == 2
    assert weeks[0]["week"] == 1
    assert weeks[0]["actual"] == 100
    assert weeks[0]["max"] == 120

    # raw SQL: view should exist and return same managers
    from sqlalchemy import text
    res = db_session.execute(text("SELECT manager_id FROM league_efficiency_leaderboard WHERE league_id = 10")).fetchall()
    assert (2,) in res and (1,) in res


# edge case: no data returns empty lists

def test_empty_queries(db_session):
    assert get_efficiency_leaderboard(league_id=999, season=2026, db=db_session) == []
    assert get_weekly_stats(league_id=999, manager_id=1, season=2026, db=db_session) == []
