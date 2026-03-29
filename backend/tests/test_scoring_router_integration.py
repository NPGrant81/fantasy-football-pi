import sys
import csv
import io
from pathlib import Path
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core.security import check_is_commissioner, get_current_user
from backend.database import get_db
from backend.main import app


TEMPLATE_IMPORT_SEASON = datetime.now().year + 1
TEMPLATE_REIMPORT_SEASON = datetime.now().year + 2


@pytest.fixture
def api_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_db(api_db):
    def override_get_db():
        try:
            yield api_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def _seed_league_and_commissioner(db):
    league = models.League(name="Scoring Router Integration League")
    db.add(league)
    db.commit()
    db.refresh(league)

    commissioner = models.User(
        username="commish-int",
        email=None,
        hashed_password="h",
        league_id=league.id,
        is_commissioner=True,
    )
    db.add(commissioner)
    db.commit()
    db.refresh(commissioner)

    return league, commissioner


def _seed_matchup_data(db, league_id: int):
    home = models.User(username="home-int", hashed_password="h", league_id=league_id)
    away = models.User(username="away-int", hashed_password="h", league_id=league_id)
    db.add_all([home, away])
    db.commit()
    db.refresh(home)
    db.refresh(away)

    home_wr = models.Player(name="Home WR", position="WR", nfl_team="AAA")
    away_wr = models.Player(name="Away WR", position="WR", nfl_team="BBB")
    db.add_all([home_wr, away_wr])
    db.commit()
    db.refresh(home_wr)
    db.refresh(away_wr)

    db.add_all(
        [
            models.DraftPick(
                owner_id=home.id,
                player_id=home_wr.id,
                league_id=league_id,
                current_status="STARTER",
            ),
            models.DraftPick(
                owner_id=away.id,
                player_id=away_wr.id,
                league_id=league_id,
                current_status="STARTER",
            ),
        ]
    )

    db.add_all(
        [
            models.PlayerWeeklyStat(
                player_id=home_wr.id,
                season=2026,
                week=5,
                stats={"receptions": 5},
                fantasy_points=0.0,
                source="test",
            ),
            models.PlayerWeeklyStat(
                player_id=away_wr.id,
                season=2026,
                week=5,
                stats={"receptions": 1},
                fantasy_points=0.0,
                source="test",
            ),
        ]
    )

    matchup = models.Matchup(
        league_id=league_id,
        week=5,
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=0.0,
        away_score=0.0,
        is_completed=False,
        game_status="IN_PROGRESS",
    )
    db.add(matchup)
    db.commit()
    db.refresh(matchup)

    return matchup


def test_import_apply_replacement_deactivates_stale_rules_and_logs_history(client, api_db):
    league, commissioner = _seed_league_and_commissioner(api_db)

    stale_rule = models.ScoringRule(
        league_id=league.id,
        season_year=2026,
        category="passing",
        event_name="passing_yards",
        description="Legacy passing yards",
        range_min=0,
        range_max=9999,
        point_value=0.04,
        calculation_type="per_unit",
        applicable_positions=["QB"],
        is_active=True,
    )
    api_db.add(stale_rule)
    api_db.commit()
    api_db.refresh(stale_rule)

    app.dependency_overrides[check_is_commissioner] = lambda: commissioner
    app.dependency_overrides[get_current_user] = lambda: commissioner

    csv_content = """Event,Range_Yds,Point_Value,PositionID
Receptions,1-999,1 points each,8004
"""

    import_response = client.post(
        "/scoring/import/apply",
        json={
            "csv_content": csv_content,
            "season_year": 2026,
            "source_platform": "espn_csv",
            "replace_existing_for_season": True,
        },
    )

    assert import_response.status_code == 200
    body = import_response.json()
    assert len(body) == 1
    assert body[0]["event_name"] == "Receptions"

    api_db.refresh(stale_rule)
    assert stale_rule.is_active is False

    history_response = client.get("/scoring/history?season_year=2026")
    assert history_response.status_code == 200
    history = history_response.json()

    change_types = {row["change_type"] for row in history}
    assert "imported" in change_types
    assert "deleted" in change_types


def test_imported_rules_drive_matchup_recalculation_scores(client, api_db):
    league, commissioner = _seed_league_and_commissioner(api_db)
    matchup = _seed_matchup_data(api_db, league.id)

    app.dependency_overrides[check_is_commissioner] = lambda: commissioner
    app.dependency_overrides[get_current_user] = lambda: commissioner

    csv_content = """Event,Range_Yds,Point_Value,PositionID
Receptions,1-999,1 points each,8004
"""

    import_response = client.post(
        "/scoring/import/apply",
        json={
            "csv_content": csv_content,
            "season_year": 2026,
            "source_platform": "espn_csv",
            "replace_existing_for_season": True,
        },
    )
    assert import_response.status_code == 200

    recalc_response = client.post(
        f"/scoring/calculate/matchups/{matchup.id}/recalculate",
        json={"season": 2026, "season_year": 2026},
    )

    assert recalc_response.status_code == 200
    recalc = recalc_response.json()
    scored_totals = sorted([float(recalc["home_score"]), float(recalc["away_score"])])
    assert scored_totals == pytest.approx([1.0, 5.0])

    api_db.refresh(matchup)
    persisted_totals = sorted([float(matchup.home_score or 0.0), float(matchup.away_score or 0.0)])
    assert persisted_totals == pytest.approx([1.0, 5.0])
    assert matchup.is_completed is True
    assert matchup.game_status == "FINAL"


def test_template_lifecycle_import_export_apply_and_recalc(client, api_db):
    league, commissioner = _seed_league_and_commissioner(api_db)
    matchup = _seed_matchup_data(api_db, league.id)

    app.dependency_overrides[check_is_commissioner] = lambda: commissioner
    app.dependency_overrides[get_current_user] = lambda: commissioner

    stale_rule = models.ScoringRule(
        league_id=league.id,
        season_year=2026,
        category="receiving",
        event_name="receptions",
        description="Legacy active rule",
        range_min=0,
        range_max=999,
        point_value=0.5,
        calculation_type="per_unit",
        applicable_positions=["WR"],
        is_active=True,
        template_id=None,
    )
    api_db.add(stale_rule)
    api_db.commit()
    api_db.refresh(stale_rule)

    csv_content = """Event,Range_Yds,Point_Value,PositionID
Receptions,1-999,2 points each,8004
"""

    import_template_response = client.post(
        "/scoring/templates/import",
        json={
            "template_name": "PPR 2x",
            "season_year": TEMPLATE_IMPORT_SEASON,
            "source_platform": "espn_csv",
            "csv_content": csv_content,
        },
    )
    assert import_template_response.status_code == 200
    template = import_template_response.json()
    template_id = int(template["id"])

    export_response = client.get(f"/scoring/templates/{template_id}/export")
    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert "Receptions" in export_payload["csv"]
    assert export_payload["template_id"] == template_id

    apply_response = client.post(
        f"/scoring/templates/{template_id}/apply",
        json={
            "season_year": 2026,
            "deactivate_existing": True,
        },
    )
    assert apply_response.status_code == 200
    applied_rules = apply_response.json()
    assert len(applied_rules) == 1
    assert applied_rules[0]["point_value"] == pytest.approx(2.0)
    assert applied_rules[0]["source"] == "template"
    assert int(applied_rules[0]["template_id"]) == template_id

    api_db.refresh(stale_rule)
    assert stale_rule.is_active is False

    recalc_response = client.post(
        f"/scoring/calculate/matchups/{matchup.id}/recalculate",
        json={"season": 2026, "season_year": 2026},
    )
    assert recalc_response.status_code == 200
    recalc = recalc_response.json()

    scored_totals = sorted([float(recalc["home_score"]), float(recalc["away_score"])])
    assert scored_totals == pytest.approx([2.0, 10.0])

    history_response = client.get("/scoring/history?season_year=2026")
    assert history_response.status_code == 200
    history = history_response.json()
    change_types = {row["change_type"] for row in history}
    assert "template_applied" in change_types
    assert "deleted" in change_types


def test_commissioner_rule_update_propagates_to_recalc_and_matchup_detail(client, api_db):
    league, commissioner = _seed_league_and_commissioner(api_db)
    matchup = _seed_matchup_data(api_db, league.id)

    app.dependency_overrides[check_is_commissioner] = lambda: commissioner
    app.dependency_overrides[get_current_user] = lambda: commissioner

    create_response = client.post(
        "/scoring/rules",
        json={
            "category": "receiving",
            "event_name": "receptions",
            "description": "Commissioner base receptions",
            "range_min": 0,
            "range_max": 999,
            "point_value": 1.0,
            "calculation_type": "per_unit",
            "applicable_positions": ["WR"],
            "position_ids": [8004],
            "season_year": 2026,
            "source": "custom",
            "is_active": True,
        },
    )
    assert create_response.status_code == 200
    created_rule = create_response.json()
    rule_id = int(created_rule["id"])

    week_recalc_response = client.post(
        "/scoring/calculate/weeks/5/recalculate",
        json={"season": 2026, "season_year": 2026},
    )
    assert week_recalc_response.status_code == 200
    week_payload = week_recalc_response.json()
    assert int(week_payload["recalculated_matchups"]) == 1

    first_scores = sorted(
        [
            float(week_payload["results"][0]["home_score"]),
            float(week_payload["results"][0]["away_score"]),
        ]
    )
    assert first_scores == pytest.approx([1.0, 5.0])

    update_response = client.put(
        f"/scoring/rules/{rule_id}",
        json={"point_value": 2.0},
    )
    assert update_response.status_code == 200
    updated_rule = update_response.json()
    assert float(updated_rule["point_value"]) == pytest.approx(2.0)

    matchup_recalc_response = client.post(
        f"/scoring/calculate/matchups/{matchup.id}/recalculate",
        json={"season": 2026, "season_year": 2026},
    )
    assert matchup_recalc_response.status_code == 200
    recalc_payload = matchup_recalc_response.json()
    recalc_scores = sorted([
        float(recalc_payload["home_score"]),
        float(recalc_payload["away_score"]),
    ])
    assert recalc_scores == pytest.approx([2.0, 10.0])

    matchup_detail_response = client.get(f"/matchups/{matchup.id}")
    assert matchup_detail_response.status_code == 200
    detail = matchup_detail_response.json()
    projected_scores = sorted([
        float(detail["home_projected"]),
        float(detail["away_projected"]),
    ])
    assert projected_scores == pytest.approx([2.0, 10.0])

    history_response = client.get(f"/scoring/history?season_year=2026&rule_id={rule_id}")
    assert history_response.status_code == 200
    history = history_response.json()
    change_types = {row["change_type"] for row in history}
    assert "created" in change_types
    assert "updated" in change_types


def test_import_replacement_propagates_without_stale_rule_leakage(client, api_db):
    league, commissioner = _seed_league_and_commissioner(api_db)
    matchup = _seed_matchup_data(api_db, league.id)

    app.dependency_overrides[check_is_commissioner] = lambda: commissioner
    app.dependency_overrides[get_current_user] = lambda: commissioner

    # Baseline active rule to be replaced.
    base_rule_response = client.post(
        "/scoring/rules",
        json={
            "category": "receiving",
            "event_name": "receptions",
            "description": "Baseline receptions rule",
            "range_min": 0,
            "range_max": 999,
            "point_value": 1.0,
            "calculation_type": "per_unit",
            "applicable_positions": ["WR"],
            "position_ids": [8004],
            "season_year": 2026,
            "source": "custom",
            "is_active": True,
        },
    )
    assert base_rule_response.status_code == 200

    baseline_recalc = client.post(
        f"/scoring/calculate/matchups/{matchup.id}/recalculate",
        json={"season": 2026, "season_year": 2026},
    )
    assert baseline_recalc.status_code == 200
    baseline_scores = sorted(
        [
            float(baseline_recalc.json()["home_score"]),
            float(baseline_recalc.json()["away_score"]),
        ]
    )
    assert baseline_scores == pytest.approx([1.0, 5.0])

    # Replace season rules from import; old active rule should be deactivated.
    replacement_csv = """Event,Range_Yds,Point_Value,PositionID
Receptions,1-999,2 points each,8004
"""
    replace_response = client.post(
        "/scoring/import/apply",
        json={
            "csv_content": replacement_csv,
            "season_year": 2026,
            "source_platform": "espn_csv",
            "replace_existing_for_season": True,
        },
    )
    assert replace_response.status_code == 200

    ruleset_response = client.get("/scoring/rulesets/current?season_year=2026")
    assert ruleset_response.status_code == 200
    ruleset = ruleset_response.json()
    assert int(ruleset["active_rule_count"]) == 1
    assert len(ruleset["rules"]) == 1
    assert float(ruleset["rules"][0]["point_value"]) == pytest.approx(2.0)

    replaced_recalc = client.post(
        f"/scoring/calculate/matchups/{matchup.id}/recalculate",
        json={"season": 2026, "season_year": 2026},
    )
    assert replaced_recalc.status_code == 200
    replaced_scores = sorted(
        [
            float(replaced_recalc.json()["home_score"]),
            float(replaced_recalc.json()["away_score"]),
        ]
    )
    assert replaced_scores == pytest.approx([2.0, 10.0])

    detail_response = client.get(f"/matchups/{matchup.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    projected_scores = sorted(
        [
            float(detail["home_projected"]),
            float(detail["away_projected"]),
        ]
    )
    assert projected_scores == pytest.approx([2.0, 10.0])

    history_response = client.get("/scoring/history?season_year=2026")
    assert history_response.status_code == 200
    change_types = {row["change_type"] for row in history_response.json()}
    assert "imported" in change_types
    assert "deleted" in change_types


def test_template_export_round_trip_preserves_scoring_parity(client, api_db):
    league, commissioner = _seed_league_and_commissioner(api_db)
    matchup = _seed_matchup_data(api_db, league.id)

    app.dependency_overrides[check_is_commissioner] = lambda: commissioner
    app.dependency_overrides[get_current_user] = lambda: commissioner

    source_csv = """Event,Range_Yds,Point_Value,PositionID
Receptions,1-999,2 points each,8004
"""

    first_import = client.post(
        "/scoring/templates/import",
        json={
            "template_name": "Round Trip Source",
            "season_year": TEMPLATE_IMPORT_SEASON,
            "source_platform": "espn_csv",
            "csv_content": source_csv,
        },
    )
    assert first_import.status_code == 200
    source_template_id = int(first_import.json()["id"])

    first_export = client.get(f"/scoring/templates/{source_template_id}/export")
    assert first_export.status_code == 200
    exported_csv = first_export.json()["csv"]

    reimport = client.post(
        "/scoring/templates/import",
        json={
            "template_name": "Round Trip Reimported",
            "season_year": TEMPLATE_REIMPORT_SEASON,
            "source_platform": "roundtrip_csv",
            "csv_content": exported_csv,
        },
    )
    assert reimport.status_code == 200
    roundtrip_template_id = int(reimport.json()["id"])

    second_export = client.get(f"/scoring/templates/{roundtrip_template_id}/export")
    assert second_export.status_code == 200

    source_rows = list(csv.DictReader(io.StringIO(exported_csv)))
    roundtrip_rows = list(csv.DictReader(io.StringIO(second_export.json()["csv"])))
    assert len(source_rows) == len(roundtrip_rows) == 1

    comparable_columns = [
        "category",
        "event_name",
        "description",
        "range_min",
        "range_max",
        "point_value",
        "calculation_type",
        "applicable_positions",
        "position_ids",
    ]
    assert {
        key: source_rows[0][key] for key in comparable_columns
    } == {
        key: roundtrip_rows[0][key] for key in comparable_columns
    }

    apply_response = client.post(
        f"/scoring/templates/{roundtrip_template_id}/apply",
        json={
            "season_year": 2026,
            "deactivate_existing": True,
        },
    )
    assert apply_response.status_code == 200

    recalc_response = client.post(
        f"/scoring/calculate/matchups/{matchup.id}/recalculate",
        json={"season": 2026, "season_year": 2026},
    )
    assert recalc_response.status_code == 200

    recalc = recalc_response.json()
    scored_totals = sorted([float(recalc["home_score"]), float(recalc["away_score"])])
    assert scored_totals == pytest.approx([2.0, 10.0])


def test_batch_upsert_rolls_back_all_changes_when_any_rule_update_fails(client, api_db):
    league, commissioner = _seed_league_and_commissioner(api_db)

    app.dependency_overrides[check_is_commissioner] = lambda: commissioner
    app.dependency_overrides[get_current_user] = lambda: commissioner

    response = client.post(
        "/scoring/rules/batch-upsert",
        json={
            "season_year": 2026,
            "replace_existing_for_season": False,
            "rules": [
                {
                    "category": "receiving",
                    "event_name": "receptions",
                    "description": "Should rollback on failure",
                    "range_min": 0,
                    "range_max": 999,
                    "point_value": 1.0,
                    "calculation_type": "per_unit",
                    "applicable_positions": ["WR"],
                    "position_ids": [8004],
                    "source": "custom",
                    "is_active": True,
                },
                {
                    "id": 999999,
                    "category": "receiving",
                    "event_name": "receiving_tds",
                    "description": "Non-existent rule should fail",
                    "range_min": 1,
                    "range_max": 999,
                    "point_value": 6.0,
                    "calculation_type": "per_unit",
                    "applicable_positions": ["WR"],
                    "position_ids": [8004],
                    "source": "custom",
                    "is_active": True,
                },
            ],
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    rules = (
        api_db.query(models.ScoringRule)
        .filter(models.ScoringRule.league_id == league.id)
        .all()
    )
    assert rules == []

    history = (
        api_db.query(models.ScoringRuleChangeLog)
        .filter(models.ScoringRuleChangeLog.league_id == league.id)
        .all()
    )
    assert history == []
