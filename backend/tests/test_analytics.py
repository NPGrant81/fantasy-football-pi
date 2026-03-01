import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.analytics import get_efficiency_leaderboard, get_weekly_stats, get_roster_strength, get_rivalry_graph


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


def make_pick(db, owner_id, league_id, player_id, status="STARTER"):
    p = models.DraftPick(
        owner_id=owner_id,
        league_id=league_id,
        player_id=player_id,
        current_status=status,
        amount=0,
    )
    db.add(p)
    db.commit()
    return p


def test_roster_strength(db_session):
    # create players with positions
    p_qb = models.Player(name="Q", position="QB", nfl_team="A")
    p_rb = models.Player(name="R", position="RB", nfl_team="A")
    p_wr = models.Player(name="W", position="WR", nfl_team="A")
    db_session.add_all([p_qb, p_rb, p_wr])
    db_session.commit()
    db_session.refresh(p_qb)
    db_session.refresh(p_rb)
    db_session.refresh(p_wr)

    # owner1 has QB and RB starters
    make_pick(db_session, owner_id=1, league_id=5, player_id=p_qb.id, status="STARTER")
    make_pick(db_session, owner_id=1, league_id=5, player_id=p_rb.id, status="STARTER")
    # owner2 has WR starter
    make_pick(db_session, owner_id=2, league_id=5, player_id=p_wr.id, status="STARTER")

    res = get_roster_strength(league_id=5, owner_id=1, other_owner_id=2, db=db_session)
    assert 1 in res and 2 in res
    assert res[1]["QB"] == 1
    assert res[1]["RB"] == 1
    assert res[1]["WR"] == 0
    assert res[2]["WR"] == 1

    # edge case: no picks
    res2 = get_roster_strength(league_id=5, owner_id=99, db=db_session)
    assert res2 == {99: {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DEF": 0, "K": 0}}


# edge case: no data returns empty lists

def test_empty_queries(db_session):
    assert get_efficiency_leaderboard(league_id=999, season=2026, db=db_session) == []
    assert get_weekly_stats(league_id=999, manager_id=1, season=2026, db=db_session) == []


def test_rivalry_graph_empty(db_session):
    """rivalry graph returns empty nodes/edges when no data exists."""
    result = get_rivalry_graph(league_id=999, db=db_session)
    assert result == {"nodes": [], "edges": []}


def test_rivalry_graph_with_matchups(db_session):
    """rivalry graph correctly aggregates head-to-head and trade data."""
    # create two users in league 20
    u1 = models.User(username="Alice", league_id=20)
    u2 = models.User(username="Bob", league_id=20)
    db_session.add_all([u1, u2])
    db_session.commit()
    db_session.refresh(u1)
    db_session.refresh(u2)

    # 3 completed matchups: u1 wins 2, u2 wins 1
    for home_score, away_score in [(120, 100), (110, 95), (90, 115)]:
        m = models.Matchup(
            league_id=20,
            home_team_id=u1.id,
            away_team_id=u2.id,
            home_score=home_score,
            away_score=away_score,
            is_completed=True,
        )
        db_session.add(m)
    db_session.commit()

    # 1 trade between u1 and u2
    t = models.TransactionHistory(
        league_id=20,
        old_owner_id=u1.id,
        new_owner_id=u2.id,
        transaction_type="trade",
    )
    db_session.add(t)
    db_session.commit()

    result = get_rivalry_graph(league_id=20, db=db_session)
    nodes = result["nodes"]
    edges = result["edges"]

    assert len(nodes) == 2
    node_labels = {n["id"]: n["label"] for n in nodes}
    assert node_labels[u1.id] == "Alice"
    assert node_labels[u2.id] == "Bob"

    assert len(edges) == 1
    edge = edges[0]
    assert edge["games"] == 3
    assert edge["trades"] == 1
    # u1 won 2, u2 won 1 – wins keys are ints (matching node ids)
    pair_key = tuple(sorted([u1.id, u2.id]))
    a, b = pair_key
    assert edge["wins"][a] + edge["wins"][b] == 3
    # verify exact distribution: 2 wins for u1, 1 win for u2
    assert edge["wins"][u1.id] == 2
    assert edge["wins"][u2.id] == 1
