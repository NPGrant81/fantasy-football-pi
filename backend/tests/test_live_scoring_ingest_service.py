from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models
from backend.services.live_scoring_ingest_service import (
    reconcile_ingested_stats_and_matchups,
    upsert_nfl_games_from_payload,
    upsert_player_weekly_stats_from_payload,
)


def _db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _payload(home_score: int, away_score: int) -> dict:
    return {
        "events": [
            {
                "id": "401888001",
                "season": {"year": 2026},
                "competitions": [
                    {
                        "date": "2026-09-10T20:20:00Z",
                        "week": {"number": 1},
                        "status": {"type": {"name": "in"}},
                        "competitors": [
                            {
                                "homeAway": "home",
                                "score": str(home_score),
                                "team": {"id": "2", "abbreviation": "BUF"},
                            },
                            {
                                "homeAway": "away",
                                "score": str(away_score),
                                "team": {"id": "9", "abbreviation": "LAR"},
                            },
                        ],
                    }
                ],
            }
        ]
    }


def _payload_with_leaders(home_score: int, away_score: int) -> dict:
    payload = _payload(home_score=home_score, away_score=away_score)
    competition = payload["events"][0]["competitions"][0]
    competition["competitors"][0]["leaders"] = [
        {
            "name": "fantasyPoints",
            "leaders": [
                {
                    "value": 12.25,
                    "athlete": {
                        "id": "2001",
                        "displayName": "Away Starter",
                        "position": {"abbreviation": "WR"},
                    },
                }
            ],
        }
    ]
    competition["competitors"][1]["leaders"] = [
        {
            "name": "fantasyPoints",
            "leaders": [
                {
                    "value": 18.5,
                    "athlete": {
                        "id": "1001",
                        "displayName": "Home Starter",
                        "position": {"abbreviation": "RB"},
                    },
                }
            ],
        }
    ]
    return payload


def _seed_league_for_reconciliation(db):
    league = models.League(name="Ingest Recalc League")
    db.add(league)
    db.flush()

    home = models.User(
        username="home-owner",
        email="home-owner@example.com",
        hashed_password="x",
        league_id=league.id,
    )
    away = models.User(
        username="away-owner",
        email="away-owner@example.com",
        hashed_password="x",
        league_id=league.id,
    )
    db.add_all([home, away])
    db.flush()

    p_home = models.Player(name="Home Starter", position="RB", nfl_team="BUF", espn_id="1001")
    p_away = models.Player(name="Away Starter", position="WR", nfl_team="LAR", espn_id="2001")
    db.add_all([p_home, p_away])
    db.flush()

    db.add_all(
        [
            models.DraftPick(
                year=2026,
                owner_id=home.id,
                player_id=p_home.id,
                league_id=league.id,
                amount=1,
                current_status="STARTER",
                is_taxi=False,
            ),
            models.DraftPick(
                year=2026,
                owner_id=away.id,
                player_id=p_away.id,
                league_id=league.id,
                amount=1,
                current_status="STARTER",
                is_taxi=False,
            ),
        ]
    )

    matchup = models.Matchup(
        week=1,
        league_id=league.id,
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=0.0,
        away_score=0.0,
        game_status="NOT_STARTED",
        is_completed=False,
    )
    db.add(matchup)
    db.commit()
    return league, matchup


def test_upsert_nfl_games_from_payload_insert_then_update():
    db = _db_session()
    try:
        first = upsert_nfl_games_from_payload(db, _payload(home_score=17, away_score=14))
        assert first["inserted"] == 1
        assert first["updated"] == 0
        assert first["missing_required_paths_count"] == 0

        second = upsert_nfl_games_from_payload(db, _payload(home_score=24, away_score=20))
        assert second["inserted"] == 0
        assert second["updated"] == 1

        game = db.query(models.NFLGame).filter(models.NFLGame.event_id == "401888001").one()
        assert game.home_score == 24
        assert game.away_score == 20
        assert game.status == "IN"
    finally:
        db.close()


def test_upsert_nfl_games_from_payload_handles_missing_contract_fields():
    db = _db_session()
    try:
        result = upsert_nfl_games_from_payload(db, {"events": [{"id": "bad"}]})
        assert result["fetched_events"] == 1
        assert result["normalized_games"] == 0
        assert result["inserted"] == 0
        assert result["updated"] == 0
        assert result["missing_required_paths_count"] > 0
    finally:
        db.close()


def test_upsert_player_weekly_stats_from_payload_persists_rows_by_espn_id():
    db = _db_session()
    try:
        league, _ = _seed_league_for_reconciliation(db)
        result = upsert_player_weekly_stats_from_payload(
            db,
            _payload_with_leaders(home_score=24, away_score=17),
            season_override=2026,
            week_override=1,
        )

        assert league.id > 0
        assert result["normalized_player_rows"] == 2
        assert result["inserted"] == 2
        assert result["updated"] == 0
        assert result["unmatched_players"] == 0

        rows = (
            db.query(models.PlayerWeeklyStat)
            .filter(
                models.PlayerWeeklyStat.season == 2026,
                models.PlayerWeeklyStat.week == 1,
                models.PlayerWeeklyStat.source == "espn_live_ingest",
            )
            .all()
        )
        assert len(rows) == 2
        assert sorted(round(float(row.fantasy_points or 0.0), 2) for row in rows) == [12.25, 18.5]
    finally:
        db.close()


def test_reconcile_ingested_stats_and_matchups_recalculates_scores_for_affected_starters():
    db = _db_session()
    try:
        league, matchup = _seed_league_for_reconciliation(db)
        upsert_result = upsert_player_weekly_stats_from_payload(
            db,
            _payload_with_leaders(home_score=24, away_score=17),
            season_override=2026,
            week_override=1,
        )

        reconcile = reconcile_ingested_stats_and_matchups(
            db,
            affected_player_ids=set(upsert_result["affected_player_ids"]),
            season=2026,
            week=1,
            season_year=2026,
            affected_weeks=set(upsert_result["affected_weeks"]),
        )

        assert reconcile["leagues_touched"] == 1
        assert reconcile["weeks_touched"] == 1
        assert reconcile["matchups_recalculated"] == 1
        assert reconcile["league_week_pairs"] == [{"league_id": league.id, "week": 1}]

        db.refresh(matchup)
        assert float(matchup.home_score or 0.0) == 18.5
        assert float(matchup.away_score or 0.0) == 12.25
        assert matchup.game_status == "FINAL"
        assert matchup.is_completed is True
    finally:
        db.close()
