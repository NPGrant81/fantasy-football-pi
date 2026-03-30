import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.analytics import (
    get_draft_value_data,
    get_efficiency_leaderboard,
    get_post_draft_outlook,
    get_player_heatmap_data,
    get_rivalry_graph,
    get_roster_strength,
    get_weekly_matchup_comparison,
    get_weekly_stats,
)


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


def make_league(db):
    l = models.League(name="TestLeague")
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def make_user(db, league_id, username="bob", team_name="TeamX"):
    u = models.User(
        username=username,
        hashed_password="pw",
        league_id=league_id,
        team_name=team_name,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


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
    assert isinstance(lb, dict)
    assert isinstance(lb["rows"], list)
    assert lb["rows"][0]["manager_id"] == 2
    assert lb["rows"][1]["manager_id"] == 1
    assert "efficiency_display" in lb["rows"][0]
    assert lb["meta"]["league_id"] == 10
    assert lb["meta"]["season"] == 2026
    assert "scoring_profile" in lb["meta"]
    # ensure JSON data is not returned by leaderboard (should be removed)
    assert "optimal_lineup_json" not in lb["rows"][0]

    # weekly stats for manager 1
    weeks = get_weekly_stats(league_id=10, manager_id=1, season=2026, db=db_session)
    # the table contains no JSON yet, but weekly stats returns max/actual
    assert len(weeks["rows"]) == 2
    assert weeks["rows"][0]["week"] == 1
    assert weeks["rows"][0]["actual"] == 100
    assert weeks["rows"][0]["max"] == 120
    assert weeks["meta"]["metric"] == "manager_weekly_stats"

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
    rows = res["rows"]
    assert 1 in rows and 2 in rows
    assert rows[1]["QB"] == 1
    assert rows[1]["RB"] == 1
    assert rows[1]["WR"] == 0
    assert rows[2]["WR"] == 1
    assert res["meta"]["metric"] == "roster_strength"

    # edge case: no picks
    res2 = get_roster_strength(league_id=5, owner_id=99, db=db_session)
    assert res2["rows"] == {99: {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DEF": 0, "K": 0}}


# edge case: no data returns empty lists

def test_empty_queries(db_session):
    assert get_efficiency_leaderboard(league_id=999, season=2026, db=db_session)["rows"] == []
    assert get_weekly_stats(league_id=999, manager_id=1, season=2026, db=db_session)["rows"] == []


def test_rivalry_graph(db_session):
    league = make_league(db_session)
    # create two users
    u1 = make_user(db_session, league.id, username="Alice", team_name="A1")
    u2 = make_user(db_session, league.id, username="Bob", team_name="B1")

    # add two completed matchups (each wins one)
    m1 = models.Matchup(
        league_id=league.id,
        week=1,
        home_team_id=u1.id,
        away_team_id=u2.id,
        home_score=100,
        away_score=90,
        is_completed=True,
    )
    m2 = models.Matchup(
        league_id=league.id,
        week=2,
        home_team_id=u2.id,
        away_team_id=u1.id,
        home_score=80,
        away_score=85,
        is_completed=True,
    )
    db_session.add_all([m1, m2])
    db_session.commit()

    # one trade transaction existing between them
    t = models.TransactionHistory(
        league_id=league.id,
        player_id=1,
        old_owner_id=u1.id,
        new_owner_id=u2.id,
        transaction_type='trade',
    )
    db_session.add(t)
    db_session.commit()

    res = get_rivalry_graph(league.id, db=db_session)
    # should return both nodes
    assert len(res['nodes']) == 2
    # edges list should have one entry for the pair
    assert len(res['edges']) == 1
    edge = res['edges'][0]
    assert edge['games'] == 2
    assert edge['trades'] == 1
    assert res['meta']['metric'] == 'league_rivalry_graph'
    # verify wins mapping contains both owners
    assert u1.id in edge['wins'] and u2.id in edge['wins']
    # ensure empty returns if no data
    empty = get_rivalry_graph(league.id + 1, db=db_session)
    assert empty['nodes'] == []
    assert empty['edges'] == []


def test_draft_value_and_heatmap_payloads(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league.id, username="TrendOwner", team_name="Trend Team")

    qb = models.Player(name="QB Alpha", position="QB", nfl_team="AAA", adp=12.0, projected_points=280)
    wr = models.Player(name="WR Beta", position="WR", nfl_team="BBB", adp=20.0, projected_points=255)
    db_session.add_all([qb, wr])
    db_session.commit()
    db_session.refresh(qb)
    db_session.refresh(wr)

    db_session.add_all(
        [
            models.DraftPick(owner_id=owner.id, league_id=league.id, player_id=qb.id, current_status="STARTER", amount=0),
            models.DraftPick(owner_id=owner.id, league_id=league.id, player_id=wr.id, current_status="STARTER", amount=0),
        ]
    )
    db_session.add_all(
        [
            models.PlayerWeeklyStat(player_id=qb.id, season=2026, week=1, fantasy_points=22.5, stats={"passing_yards": 280}, source="test"),
            models.PlayerWeeklyStat(player_id=qb.id, season=2026, week=2, fantasy_points=18.0, stats={"passing_yards": 240}, source="test"),
            models.PlayerWeeklyStat(player_id=wr.id, season=2026, week=1, fantasy_points=16.2, stats={"receptions": 6}, source="test"),
            models.PlayerWeeklyStat(player_id=wr.id, season=2026, week=2, fantasy_points=19.8, stats={"receptions": 8}, source="test"),
        ]
    )
    db_session.commit()

    draft_value = get_draft_value_data(league_id=league.id, season=2026, limit=20, db=db_session)
    assert draft_value["rows"]
    assert draft_value["meta"]["metric"] == "draft_value_analysis"
    assert {row["player_name"] for row in draft_value["rows"]} >= {"QB Alpha", "WR Beta"}

    heatmap = get_player_heatmap_data(league_id=league.id, season=2026, limit=5, weeks=4, db=db_session)
    assert heatmap["rows"]
    assert len(heatmap["week_labels"]) == 2
    assert heatmap["meta"]["metric"] == "player_performance_heatmap"


def test_weekly_matchup_comparison_payload(db_session):
    league = make_league(db_session)
    home = make_user(db_session, league.id, username="Home", team_name="Home Team")
    away = make_user(db_session, league.id, username="Away", team_name="Away Team")

    db_session.add_all(
        [
            models.Matchup(
                league_id=league.id,
                week=1,
                home_team_id=home.id,
                away_team_id=away.id,
                home_score=123.4,
                away_score=117.2,
                is_completed=True,
            ),
            models.Matchup(
                league_id=league.id,
                week=2,
                home_team_id=away.id,
                away_team_id=home.id,
                home_score=101.0,
                away_score=110.5,
                is_completed=True,
            ),
        ]
    )
    db_session.commit()

    comparison = get_weekly_matchup_comparison(
        league_id=league.id,
        season=2026,
        start_week=1,
        end_week=2,
        db=db_session,
    )
    assert comparison["meta"]["metric"] == "weekly_matchup_comparison"


def test_post_draft_outlook_payload_and_owner_focus(db_session):
    league = make_league(db_session)
    owner_a = make_user(db_session, league.id, username="OutlookA", team_name="Alpha")
    owner_b = make_user(db_session, league.id, username="OutlookB", team_name="Bravo")

    qb = models.Player(name="Outlook QB", position="QB", nfl_team="AAA", projected_points=275.0)
    rb = models.Player(name="Outlook RB", position="RB", nfl_team="BBB", projected_points=215.0)
    wr = models.Player(name="Outlook WR", position="WR", nfl_team="CCC", projected_points=190.0)
    te = models.Player(name="Outlook TE", position="TE", nfl_team="DDD", projected_points=140.0)
    db_session.add_all([qb, rb, wr, te])
    db_session.commit()
    db_session.refresh(qb)
    db_session.refresh(rb)
    db_session.refresh(wr)
    db_session.refresh(te)

    db_session.add_all(
        [
            models.DraftPick(owner_id=owner_a.id, league_id=league.id, player_id=qb.id, current_status="STARTER", amount=10),
            models.DraftPick(owner_id=owner_a.id, league_id=league.id, player_id=rb.id, current_status="STARTER", amount=10),
            models.DraftPick(owner_id=owner_a.id, league_id=league.id, player_id=wr.id, current_status="STARTER", amount=10),
            models.DraftPick(owner_id=owner_b.id, league_id=league.id, player_id=te.id, current_status="STARTER", amount=10),
        ]
    )
    db_session.commit()

    payload = get_post_draft_outlook(
        league_id=league.id,
        owner_id=owner_a.id,
        season=2026,
        db=db_session,
    )

    assert payload["meta"]["metric"] == "post_draft_season_outlook"
    assert len(payload["team_rows"]) == 2
    assert payload["owner_focus"] is not None
    assert payload["owner_focus"]["owner_id"] == owner_a.id
    assert "summary" in payload["owner_focus"]


def test_post_draft_outlook_rejects_owner_outside_league(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league.id, username="LeagueOwner")

    other_league = models.League(name="OtherLeague")
    db_session.add(other_league)
    db_session.commit()
    db_session.refresh(other_league)
    outsider = make_user(db_session, other_league.id, username="Outsider")

    with pytest.raises(HTTPException) as exc:
        get_post_draft_outlook(
            league_id=league.id,
            owner_id=outsider.id,
            season=2026,
            db=db_session,
        )

    assert exc.value.status_code == 404


def test_weekly_matchup_comparison_ignores_malformed_rows(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league.id, username="Owner", team_name="Owner Team")

    # One valid matchup plus malformed legacy rows should not crash payload generation.
    db_session.add_all(
        [
            models.Matchup(
                league_id=league.id,
                week=1,
                home_team_id=owner.id,
                away_team_id=owner.id,
                home_score=99.0,
                away_score=97.0,
                is_completed=True,
            ),
            models.Matchup(
                league_id=league.id,
                week=2,
                home_team_id=None,
                away_team_id=owner.id,
                home_score=101.0,
                away_score=88.0,
                is_completed=True,
            ),
        ]
    )
    db_session.commit()

    comparison = get_weekly_matchup_comparison(
        league_id=league.id,
        season=2026,
        start_week=1,
        end_week=5,
        db=db_session,
    )

    assert comparison["meta"]["metric"] == "weekly_matchup_comparison"
    assert len(comparison["rows"]) == 1
    assert comparison["rows"][0]["week"] == 1


def test_rivalry_graph_ignores_null_trade_rows(db_session):
    league = make_league(db_session)
    u1 = make_user(db_session, league.id, username="A", team_name="A Team")
    u2 = make_user(db_session, league.id, username="B", team_name="B Team")

    db_session.add(
        models.Matchup(
            league_id=league.id,
            week=1,
            home_team_id=u1.id,
            away_team_id=u2.id,
            home_score=120.0,
            away_score=110.0,
            is_completed=True,
        )
    )
    db_session.add_all(
        [
            models.TransactionHistory(
                league_id=league.id,
                player_id=1,
                old_owner_id=u1.id,
                new_owner_id=u2.id,
                transaction_type="trade",
            ),
            models.TransactionHistory(
                league_id=league.id,
                player_id=2,
                old_owner_id=None,
                new_owner_id=u2.id,
                transaction_type="trade",
            ),
        ]
    )
    db_session.commit()

    res = get_rivalry_graph(league.id, db=db_session)
    assert len(res["edges"]) == 1
    assert res["edges"][0]["trades"] == 1
