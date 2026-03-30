import sys
from pathlib import Path
import secrets
import logging
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from fastapi import HTTPException
from backend.routers.league import get_league_budgets, get_league_settings, update_league_budgets, BudgetUpdateRequest, BudgetEntry, DraftYearUpdateRequest, set_league_draft_year, get_ledger_statement, LeagueConfigFull, ScoringRuleSchema, validate_lineup_rules, canonicalize_lineup_slots, get_matchup_records, get_history_team_owner_map, upsert_history_team_owner_map, HistoryTeamOwnerMapUpsertRequest, HistoryTeamOwnerMapUpsertItem, get_all_time_series_records, ask_history_question, HistoryQuestionRequest, delete_history_team_owner_map_row, get_unmapped_series_keys, get_history_owner_gap_report, join_league
from backend.routers.draft import _get_owner_total_budget


TEST_ACTIVE_SEASON = datetime.now().year
TEST_NEAR_FUTURE_SEASON = TEST_ACTIVE_SEASON + 1


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_league(db):
    l = models.League(name=f"L-{secrets.token_hex(4)}")
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def make_user(db, league, username="u", team="t"):
    u = models.User(username=username, hashed_password="pw", league_id=league.id, team_name=team)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_get_league_budgets_empty(db_session):
    league = make_league(db_session)
    # no budgets exist yet
    u1 = make_user(db_session, league, "a", "TeamA")
    u2 = make_user(db_session, league, "b", "TeamB")

    result = get_league_budgets(league_id=league.id, year=2026, current_user=u1, db=db_session)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["team_name"] in ("TeamA", "TeamB")
    assert result[0]["total_budget"] is None


def test_get_league_budgets_with_data(db_session):
    league = make_league(db_session)
    u1 = make_user(db_session, league, "a", "TeamA")
    u2 = make_user(db_session, league, "b", "TeamB")
    # insert budgets
    db_session.add(models.DraftBudget(league_id=league.id, owner_id=u1.id, year=2026, total_budget=150))
    db_session.add(models.DraftBudget(league_id=league.id, owner_id=u2.id, year=2026, total_budget=175))
    db_session.commit()

    result = get_league_budgets(league_id=league.id, year=2026, current_user=u1, db=db_session)
    assert len(result) == 2
    # budgets should be filled
    budgets = {r["owner_id"]: r["total_budget"] for r in result}
    assert budgets[u1.id] == 150
    assert budgets[u2.id] == 175


def test_get_league_budgets_uses_ledger_when_present(db_session):
    league = make_league(db_session)
    u1 = make_user(db_session, league, "ledger-a", "TeamA")
    u2 = make_user(db_session, league, "ledger-b", "TeamB")
    u3 = make_user(db_session, league, "legacy-only", "TeamC")

    # legacy fallback row for owner without ledger credits
    db_session.add(
        models.DraftBudget(
            league_id=league.id,
            owner_id=u3.id,
            year=2027,
            total_budget=160,
        )
    )

    # ledger history for u1: +200 allocation, -25 trade out => 175
    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=2027,
            currency_type="DRAFT_DOLLARS",
            amount=200,
            from_owner_id=None,
            to_owner_id=u1.id,
            transaction_type="SEASON_ALLOCATION",
            reference_type="LEAGUE_BUDGETS",
            reference_id=f"{league.id}:2027:{u1.id}",
        )
    )
    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=2027,
            currency_type="DRAFT_DOLLARS",
            amount=25,
            from_owner_id=u1.id,
            to_owner_id=u2.id,
            transaction_type="TRADE_DOLLARS",
            reference_type="TRADE_PROPOSAL",
            reference_id="t1",
        )
    )
    db_session.commit()

    result = get_league_budgets(league_id=league.id, year=2027, current_user=u1, db=db_session)
    budgets = {r["owner_id"]: r["total_budget"] for r in result}
    assert budgets[u1.id] == 175
    assert budgets[u2.id] == 25
    # u3 has no incoming ledger credits for this season, so fallback applies
    assert budgets[u3.id] == 160


def test_update_league_budgets_writes_ledger_and_keeps_path(db_session):
    league = make_league(db_session)
    comm = models.User(
        username="comm",
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=True,
    )
    db_session.add(comm)
    db_session.commit()
    db_session.refresh(comm)

    u1 = make_user(db_session, league, "owner-a", "TeamA")
    u2 = make_user(db_session, league, "owner-b", "TeamB")

    payload = BudgetUpdateRequest(
        year=2028,
        budgets=[
            BudgetEntry(owner_id=u1.id, total_budget=210),
            BudgetEntry(owner_id=u2.id, total_budget=190),
        ],
    )
    res = update_league_budgets(
        league_id=league.id,
        payload=payload,
        current_user=comm,
        db=db_session,
    )
    assert res["year"] == 2028

    ledger_rows = (
        db_session.query(models.EconomicLedger)
        .filter(
            models.EconomicLedger.league_id == league.id,
            models.EconomicLedger.season_year == 2028,
            models.EconomicLedger.currency_type == "DRAFT_DOLLARS",
        )
        .all()
    )
    assert len(ledger_rows) == 2

    budgets = get_league_budgets(league_id=league.id, year=2028, current_user=comm, db=db_session)
    budget_map = {r["owner_id"]: r["total_budget"] for r in budgets}
    assert budget_map[u1.id] == 210
    assert budget_map[u2.id] == 190


def test_non_commissioner_cannot_update_budgets(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league, "owner-only", "OwnerOnly")

    payload = BudgetUpdateRequest(
        year=2028,
        budgets=[BudgetEntry(owner_id=owner.id, total_budget=200)],
    )

    with pytest.raises(HTTPException) as exc:
        update_league_budgets(
            league_id=league.id,
            payload=payload,
            current_user=owner,
            db=db_session,
        )

    assert exc.value.status_code == 403


def test_get_league_budgets_rejects_other_league_user(db_session):
    league_a = make_league(db_session)
    league_b = make_league(db_session)
    owner_a = make_user(db_session, league_a, "owner-a", "A")
    owner_b = make_user(db_session, league_b, "owner-b", "B")

    with pytest.raises(HTTPException) as exc:
        get_league_budgets(
            league_id=league_a.id,
            year=2028,
            current_user=owner_b,
            db=db_session,
        )

    assert exc.value.status_code == 403


def test_join_league_rejects_non_superuser_with_existing_league(db_session):
    source_league = make_league(db_session)
    target_league = make_league(db_session)
    user = make_user(db_session, source_league, "join-owner", "JoinTeam")

    with pytest.raises(HTTPException) as exc:
        join_league(league_id=target_league.id, current_user=user, db=db_session)

    assert exc.value.status_code == 403


def test_join_league_allows_non_superuser_same_league_idempotent(db_session):
    league = make_league(db_session)
    user = make_user(db_session, league, "same-league-owner", "SameLeague")

    response = join_league(league_id=league.id, current_user=user, db=db_session)
    db_session.refresh(user)

    assert user.league_id == league.id
    assert "Welcome to" in response["message"]


def test_join_league_allows_first_time_user_without_league(db_session):
    target_league = make_league(db_session)
    user = models.User(
        username="first-time-owner",
        hashed_password="pw",
        league_id=None,
        team_name="FirstTime",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    response = join_league(league_id=target_league.id, current_user=user, db=db_session)
    db_session.refresh(user)

    assert user.league_id == target_league.id
    assert "Welcome to" in response["message"]


def test_join_league_allows_superuser_switch(db_session):
    source_league = make_league(db_session)
    target_league = make_league(db_session)
    superuser = models.User(
        username="super-join",
        hashed_password="pw",
        league_id=source_league.id,
        team_name="Super",
        is_superuser=True,
    )
    db_session.add(superuser)
    db_session.commit()
    db_session.refresh(superuser)

    response = join_league(
        league_id=target_league.id,
        current_user=superuser,
        db=db_session,
    )
    db_session.refresh(superuser)

    assert superuser.league_id == target_league.id
    assert "Welcome to" in response["message"]


def test_update_league_budgets_rejects_owner_outside_league(db_session):
    league = make_league(db_session)
    other_league = make_league(db_session)
    comm = models.User(
        username="comm-validate-owner",
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=True,
    )
    db_session.add(comm)
    db_session.commit()
    db_session.refresh(comm)

    owner_in_league = make_user(db_session, league, "league-owner", "TeamL")
    owner_outside = make_user(db_session, other_league, "outside-owner", "TeamO")

    payload = BudgetUpdateRequest(
        year=2028,
        budgets=[
            BudgetEntry(owner_id=owner_in_league.id, total_budget=210),
            BudgetEntry(owner_id=owner_outside.id, total_budget=175),
        ],
    )

    with pytest.raises(HTTPException) as exc:
        update_league_budgets(
            league_id=league.id,
            payload=payload,
            current_user=comm,
            db=db_session,
        )

    assert exc.value.status_code == 400
    assert "owner_id values are not in league" in exc.value.detail


def test_commissioner_cannot_mutate_other_league_budget_or_draft_year(db_session):
    league_a = make_league(db_session)
    league_b = make_league(db_session)
    comm_a = models.User(
        username="comm-a",
        hashed_password="pw",
        league_id=league_a.id,
        is_commissioner=True,
    )
    db_session.add(comm_a)
    db_session.commit()
    db_session.refresh(comm_a)

    owner_b = make_user(db_session, league_b, "owner-b", "TeamB")

    with pytest.raises(HTTPException) as exc_budget:
        update_league_budgets(
            league_id=league_b.id,
            payload=BudgetUpdateRequest(
                year=2028,
                budgets=[BudgetEntry(owner_id=owner_b.id, total_budget=200)],
            ),
            current_user=comm_a,
            db=db_session,
        )
    assert exc_budget.value.status_code == 403

    with pytest.raises(HTTPException) as exc_year:
        set_league_draft_year(
            league_id=league_b.id,
            payload=DraftYearUpdateRequest(year=2028),
            current_user=comm_a,
            db=db_session,
        )
    assert exc_year.value.status_code == 403


def test_year_validation_applies_to_draft_budget_and_statement(db_session):
    league = make_league(db_session)
    comm = models.User(
        username="comm-year-validate",
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=True,
    )
    db_session.add(comm)
    db_session.commit()
    db_session.refresh(comm)

    owner = make_user(db_session, league, "owner-year", "TeamY")

    with pytest.raises(HTTPException) as exc_draft_year:
        set_league_draft_year(
            league_id=league.id,
            payload=DraftYearUpdateRequest(year=1999),
            current_user=comm,
            db=db_session,
        )
    assert exc_draft_year.value.status_code == 400

    with pytest.raises(HTTPException) as exc_budget_year:
        update_league_budgets(
            league_id=league.id,
            payload=BudgetUpdateRequest(
                year=1999,
                budgets=[BudgetEntry(owner_id=owner.id, total_budget=200)],
            ),
            current_user=comm,
            db=db_session,
        )
    assert exc_budget_year.value.status_code == 400

    with pytest.raises(HTTPException) as exc_statement_year:
        get_ledger_statement(
            league_id=league.id,
            owner_id=owner.id,
            currency_type=None,
            season_year=1999,
            limit=10,
            current_user=comm,
            db=db_session,
        )
    assert exc_statement_year.value.status_code == 400


def test_draft_budget_total_ignores_keeper_lock_in_base(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league, "owner-keeper", "TeamK")

    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=2029,
            currency_type="DRAFT_DOLLARS",
            amount=200,
            from_owner_id=None,
            to_owner_id=owner.id,
            transaction_type="SEASON_ALLOCATION",
            reference_type="LEAGUE_BUDGETS",
            reference_id=f"{league.id}:2029:{owner.id}",
        )
    )
    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=2029,
            currency_type="DRAFT_DOLLARS",
            amount=20,
            from_owner_id=owner.id,
            to_owner_id=None,
            transaction_type="KEEPER_LOCK",
            reference_type="LEAGUE_KEEPER_LOCK",
            reference_id=f"{league.id}:2029:{owner.id}",
        )
    )
    db_session.commit()

    # Draft base budget should remain 200; keeper spend is handled separately in draft logic.
    assert _get_owner_total_budget(
        db_session,
        league_id=league.id,
        owner_id=owner.id,
        draft_year=2029,
    ) == 200


def test_get_league_settings_defaults(db_session):
    league = make_league(db_session)
    # no settings row initially
    assert db_session.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league.id).first() is None

    cfg = get_league_settings(league_id=league.id, db=db_session)
    # should return the hard-coded defaults from the router
    assert cfg.roster_size == 14
    assert cfg.salary_cap == 200
    assert isinstance(cfg.starting_slots, dict)
    assert cfg.starting_slots.get("QB") == 1

    # the defaults should also now be persisted to the database
    settings = db_session.query(models.LeagueSettings).filter(models.LeagueSettings.league_id == league.id).first()
    assert settings is not None
    assert settings.roster_size == 14


def test_get_league_settings_existing(db_session):
    league = make_league(db_session)
    # create a custom settings record to ensure the router returns it unchanged
    custom = models.LeagueSettings(
        league_id=league.id,
        roster_size=22,
        salary_cap=500,
        starting_slots={"QB": 2},
    )
    db_session.add(custom)
    db_session.commit()

    cfg = get_league_settings(league_id=league.id, db=db_session)
    assert cfg.roster_size == 22
    assert cfg.salary_cap == 500
    assert cfg.starting_slots.get("QB") == 2


def test_validate_lineup_rules_rejects_starter_counts_above_max_limits():
    config = LeagueConfigFull(
        roster_size=14,
        salary_cap=200,
        starting_slots={
            "QB": 1,
            "RB": 5,
            "WR": 2,
            "TE": 1,
            "K": 0,
            "DEF": 0,
            "FLEX": 1,
            "ACTIVE_ROSTER_SIZE": 9,
            "MAX_QB": 2,
            "MAX_RB": 4,
            "MAX_WR": 5,
            "MAX_TE": 3,
            "MAX_K": 0,
            "MAX_DEF": 1,
            "MAX_FLEX": 1,
            "ALLOW_PARTIAL_LINEUP": 0,
            "REQUIRE_WEEKLY_SUBMIT": 1,
        },
        waiver_deadline="Wed 11PM",
        starting_waiver_budget=100,
        waiver_system="FAAB",
        waiver_tiebreaker="standings",
        trade_deadline=None,
        draft_year=2026,
        scoring_rules=[
            ScoringRuleSchema(
                category="passing",
                event_name="TD",
                point_value=4,
            )
        ],
    )

    with pytest.raises(HTTPException, match="RB starter count cannot exceed MAX_RB"):
        validate_lineup_rules(config)


def test_canonicalize_lineup_slots_rewrites_stale_hidden_minimums():
    normalized = canonicalize_lineup_slots(
        {
            "QB": 2,
            "RB": 5,
            "WR": 2,
            "TE": 1,
            "K": 1,
            "DEF": 1,
            "FLEX": 1,
            "ALLOW_PARTIAL_LINEUP": 0,
            "REQUIRE_WEEKLY_SUBMIT": 1,
            "ACTIVE_ROSTER_SIZE": 9,
            "MAX_QB": 2,
            "MAX_RB": 4,
            "MAX_WR": 5,
            "MAX_TE": 3,
            "MAX_K": 0,
            "MAX_DEF": 1,
            "MAX_FLEX": 0,
            "TAXI_SIZE": 0,
        }
    )

    assert normalized["QB"] == 1
    assert normalized["RB"] == 2
    assert normalized["WR"] == 2
    assert normalized["TE"] == 1
    assert normalized["K"] == 0
    assert normalized["DEF"] == 1
    assert normalized["FLEX"] == 0


def test_get_ledger_statement_owner_self(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league, "ledger-self", "TeamSelf")
    other = make_user(db_session, league, "ledger-other", "TeamOther")

    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=TEST_NEAR_FUTURE_SEASON,
            currency_type="DRAFT_DOLLARS",
            amount=200,
            from_owner_id=None,
            to_owner_id=owner.id,
            transaction_type="SEASON_ALLOCATION",
            reference_type="LEAGUE_BUDGETS",
            reference_id=f"{league.id}:{TEST_NEAR_FUTURE_SEASON}:{owner.id}",
        )
    )
    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=TEST_NEAR_FUTURE_SEASON,
            currency_type="DRAFT_DOLLARS",
            amount=15,
            from_owner_id=owner.id,
            to_owner_id=other.id,
            transaction_type="TRADE_DOLLARS",
            reference_type="TRADE_PROPOSAL",
            reference_id="44",
        )
    )
    db_session.commit()

    statement = get_ledger_statement(
        league_id=league.id,
        owner_id=None,
        currency_type="DRAFT_DOLLARS",
        season_year=TEST_NEAR_FUTURE_SEASON,
        limit=100,
        current_user=owner,
        db=db_session,
    )
    assert statement.owner_id == owner.id
    assert statement.balance == 185
    assert statement.entry_count == 2
    directions = {e.direction for e in statement.entries}
    assert directions == {"CREDIT", "DEBIT"}


def test_get_ledger_statement_owner_cannot_view_other(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league, "owner-1", "T1")
    other = make_user(db_session, league, "owner-2", "T2")

    with pytest.raises(HTTPException) as exc:
        get_ledger_statement(
            league_id=league.id,
            owner_id=other.id,
            currency_type=None,
            season_year=None,
            limit=50,
            current_user=owner,
            db=db_session,
        )
    assert exc.value.status_code == 403


def test_get_ledger_statement_commissioner_can_view_owner(db_session):
    league = make_league(db_session)
    comm = models.User(
        username="comm-statement",
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=True,
    )
    db_session.add(comm)
    db_session.commit()
    db_session.refresh(comm)

    owner = make_user(db_session, league, "owner-statement", "TO")

    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=TEST_NEAR_FUTURE_SEASON,
            currency_type="FAAB",
            amount=100,
            from_owner_id=None,
            to_owner_id=owner.id,
            transaction_type="SEASON_ALLOCATION",
            reference_type="LEAGUE_SETTINGS",
            reference_id=f"{league.id}:{TEST_NEAR_FUTURE_SEASON}:faab",
        )
    )
    db_session.commit()

    statement = get_ledger_statement(
        league_id=league.id,
        owner_id=owner.id,
        currency_type="FAAB",
        season_year=TEST_NEAR_FUTURE_SEASON,
        limit=25,
        current_user=comm,
        db=db_session,
    )
    assert statement.owner_id == owner.id
    assert statement.balance == 100
    assert statement.entry_count == 1
    assert statement.entries[0].direction == "CREDIT"


def test_get_matchup_records_dedupes_and_enriches_owner_names(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "history-user", "Step Brothers")

    # Extra owner record for user-based fallback mapping.
    make_user(db_session, league, "chester", "Tuamanji")

    db_session.add(
        models.LeagueHistoryTeamOwnerMap(
            league_id=league.id,
            season=2023,
            team_name="Tuamanji",
            team_name_key="tuamanji",
            owner_name="Chester",
        )
    )

    payload = {
        "record_year": 2023,
        "record_week": 13,
        "away_franchise_raw": "Step Brothers",
        "away_points": 445.4,
        "home_franchise_raw": "Tuamanji",
        "home_points": 606.8,
        "combined_score": 1052.2,
    }

    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_matchup_records_normalized",
            season=2023,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="match-1",
            record_json=payload,
        )
    )
    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_matchup_records_normalized",
            season=2023,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="match-2",
            record_json=dict(payload),
        )
    )
    db_session.commit()

    response = get_matchup_records(league_id=league.id, db=db_session, current_user=current_user)

    assert response.count == 1
    assert len(response.records) == 1
    first = response.records[0]
    assert first["home_owner_name"] == "Chester"
    assert first["away_owner_name"] == "history-user"


def test_get_matchup_records_ignores_placeholder_owner_mapping_when_user_fallback_exists(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "history-user", "Step Brothers")

    make_user(db_session, league, "chester", "Tuamanji")

    db_session.add(
        models.LeagueHistoryTeamOwnerMap(
            league_id=league.id,
            season=2023,
            team_name="Tuamanji",
            team_name_key="tuamanji",
            owner_name="Tuamanji",
        )
    )

    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_matchup_records_normalized",
            season=2023,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="match-placeholder-owner",
            record_json={
                "record_year": 2023,
                "record_week": 13,
                "away_franchise_raw": "Step Brothers",
                "away_points": 445.4,
                "home_franchise_raw": "Tuamanji",
                "home_points": 606.8,
                "combined_score": 1052.2,
            },
        )
    )
    db_session.commit()

    response = get_matchup_records(league_id=league.id, db=db_session, current_user=current_user)

    assert response.count == 1
    first = response.records[0]
    assert first["home_owner_name"] == "chester"


def test_get_matchup_records_denies_other_league_access(db_session):
    league_a = make_league(db_session)
    league_b = make_league(db_session)

    user_a = make_user(db_session, league_a, "owner-a", "Team A")
    make_user(db_session, league_b, "owner-b", "Team B")

    with pytest.raises(HTTPException) as exc:
        get_matchup_records(league_id=league_b.id, db=db_session, current_user=user_a)

    assert exc.value.status_code == 403


def test_get_matchup_records_ignores_malformed_record_json_rows(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "match-malformed", "Good Team")

    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_matchup_records_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="match-malformed-1",
            record_json="bad-match-payload",
        )
    )
    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_matchup_records_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="match-valid-1",
            record_json={
                "record_year": 2024,
                "record_week": 1,
                "away_franchise_raw": "Good Team",
                "away_points": 101.5,
                "home_franchise_raw": "Other Team",
                "home_points": 95.3,
                "combined_score": 196.8,
            },
        )
    )
    db_session.commit()

    response = get_matchup_records(league_id=league.id, db=db_session, current_user=current_user)
    assert response.count == 1
    assert response.records[0]["record_week"] == 1


def test_upsert_and_list_history_team_owner_map(db_session):
    league = make_league(db_session)
    comm = models.User(
        username="history-comm",
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=True,
    )
    db_session.add(comm)
    db_session.commit()
    db_session.refresh(comm)

    owner = make_user(db_session, league, "owner-name", "Legacy Team")

    payload = HistoryTeamOwnerMapUpsertRequest(
        mappings=[
            HistoryTeamOwnerMapUpsertItem(
                season=2019,
                team_name="Legacy Team",
                owner_name="Chester",
                owner_id=owner.id,
                notes="historical override",
            )
        ]
    )
    upsert_result = upsert_history_team_owner_map(
        league_id=league.id,
        payload=payload,
        current_user=comm,
        db=db_session,
    )

    assert upsert_result["created"] == 1
    assert upsert_result["updated"] == 0

    list_result = get_history_team_owner_map(
        league_id=league.id,
        current_user=comm,
        db=db_session,
    )
    assert list_result["count"] == 1
    assert list_result["mappings"][0]["team_name"] == "Legacy Team"
    assert list_result["mappings"][0]["owner_name"] == "Chester"
    assert list_result["mappings"][0]["team_name_key"] == "legacy team"


def test_all_time_series_records_enrich_owner_fields(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "history-reader", "Current Team")

    db_session.add(
        models.LeagueHistoryTeamOwnerMap(
            league_id=league.id,
            season=2019,
            team_name="mfl_o_171",
            team_name_key="mfl o 171",
            owner_name="Chester",
        )
    )
    db_session.add(
        models.LeagueHistoryTeamOwnerMap(
            league_id=league.id,
            season=2019,
            team_name="Gridiron Brothers",
            team_name_key="gridiron brothers",
            owner_name="Alex",
        )
    )
    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_all_time_series_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="series-1",
            record_json={
                "series_season": 2019,
                "source_url": "https://www46.myfantasyleague.com/2026/options?L=11422&O=171",
                "opponent_franchise_raw": "Gridiron Brothers",
                "season_w_l_t_raw": "2-1-0",
                "total_w_l_t_raw": "14-21-0",
                "total_pct": 0.4,
            },
        )
    )
    db_session.commit()

    response = get_all_time_series_records(league_id=league.id, db=db_session, current_user=current_user)
    assert response.count == 1
    row = response.records[0]
    assert row["perspective_owner_name"] == "Chester"
    assert row["opponent_owner_name"] == "Alex"


def test_all_time_series_records_enrich_owner_fields_nearest_season_fallback(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "history-reader-fallback", "Current Team")

    db_session.add(
        models.LeagueHistoryTeamOwnerMap(
            league_id=league.id,
            season=2025,
            team_name="Gridiron Brothers",
            team_name_key="gridiron brothers",
            owner_name="Alex",
        )
    )
    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_all_time_series_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="series-fallback-1",
            record_json={
                "series_season": 2024,
                "source_url": "https://www46.myfantasyleague.com/2026/options?L=11422&O=171",
                "opponent_franchise_raw": "Gridiron Brothers",
                "season_w_l_t_raw": "2-1-0",
                "total_w_l_t_raw": "14-21-0",
                "total_pct": 0.4,
            },
        )
    )
    db_session.commit()

    response = get_all_time_series_records(league_id=league.id, db=db_session, current_user=current_user)
    assert response.count == 1
    row = response.records[0]
    assert row["opponent_owner_name"] == "Alex"


def test_ask_history_question_answers_most_points_query(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "history-reader-2", "Reader Team")

    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_player_records_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="player-record-1",
            record_json={
                "record_year": 2019,
                "record_week": 11,
                "player_name": "Player Prime",
                "points": 48.25,
            },
        )
    )
    db_session.commit()

    response = ask_history_question(
        league_id=league.id,
        payload=HistoryQuestionRequest(question="who had the most points in 2019?"),
        db=db_session,
        current_user=current_user,
    )
    assert response["intent"] == "player-most-points"
    assert "Player Prime" in response["answer"]


def test_delete_history_owner_map_row(db_session):
    league = make_league(db_session)
    comm = models.User(
        username="delete-comm",
        hashed_password="pw",
        league_id=league.id,
        is_commissioner=True,
    )
    db_session.add(comm)
    db_session.commit()
    db_session.refresh(comm)

    row = models.LeagueHistoryTeamOwnerMap(
        league_id=league.id,
        season=2020,
        team_name="Delete Me",
        team_name_key="delete me",
        owner_name="Gone",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    row_id = row.id

    result = delete_history_team_owner_map_row(
        league_id=league.id,
        map_id=row_id,
        db=db_session,
        current_user=comm,
    )
    assert result["deleted"] is True
    assert result["id"] == row_id

    remaining = (
        db_session.query(models.LeagueHistoryTeamOwnerMap)
        .filter(models.LeagueHistoryTeamOwnerMap.id == row_id)
        .first()
    )
    assert remaining is None


def test_get_unmapped_series_keys(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "unmapped-reader", "Unmapped Team")

    # Add a series record with source token mfl_o_200
    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_all_time_series_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="unmapped-series-1",
            record_json={
                "series_season": 2020,
                "source_url": "https://www46.myfantasyleague.com/2026/options?L=11422&O=200",
            },
        )
    )
    db_session.commit()

    result = get_unmapped_series_keys(league_id=league.id, db=db_session, current_user=current_user)
    assert result["unmapped_count"] == 1
    assert result["unmapped"][0]["source_token"] == "mfl o 200"
    assert result["unmapped"][0]["record_count"] == 1
    assert result["mapped_count"] == 0


def test_get_all_time_series_records_ignores_malformed_record_json_rows(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "series-malformed", "Good Team")

    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_all_time_series_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="series-malformed-1",
            record_json=["bad", "series", "payload"],
        )
    )
    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_all_time_series_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="series-valid-1",
            record_json={
                "series_season": 2024,
                "source_url": "https://www46.myfantasyleague.com/2026/options?L=11422&O=200",
                "opponent_franchise_raw": "Other Team",
                "season_w_l_t_raw": "1-0-0",
                "total_w_l_t_raw": "3-1-0",
                "total_pct": 0.75,
            },
        )
    )
    db_session.commit()

    response = get_all_time_series_records(league_id=league.id, db=db_session, current_user=current_user)
    assert response.count == 1
    assert response.records[0]["series_season"] == 2024


def test_get_history_owner_gap_report_surfaces_placeholder_and_unresolved_rows(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "gap-reader", "Current Team")
    make_user(db_session, league, "chester", "Tuamanji")

    db_session.add(
        models.LeagueHistoryTeamOwnerMap(
            league_id=league.id,
            season=2023,
            team_name="Tuamanji",
            team_name_key="tuamanji",
            owner_name="Tuamanji",
        )
    )
    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_matchup_records_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="owner-gap-match-1",
            record_json={
                "record_year": 2023,
                "record_week": 8,
                "away_franchise_raw": "Ghost Team",
                "away_points": 101.2,
                "home_franchise_raw": "Tuamanji",
                "home_points": 111.4,
                "combined_score": 212.6,
            },
        )
    )
    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_all_time_series_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="owner-gap-series-1",
            record_json={
                "series_season": 2023,
                "source_url": "https://www46.myfantasyleague.com/2026/options?L=11422&O=200",
                "opponent_franchise_raw": "Ghost Team",
                "season_w_l_t_raw": "1-2-0",
                "total_w_l_t_raw": "4-8-0",
                "total_pct": 0.333,
            },
        )
    )
    db_session.commit()

    result = get_history_owner_gap_report(league_id=league.id, db=db_session, current_user=current_user)

    assert result["summary"]["placeholder_mapping_count"] == 1
    assert result["summary"]["unresolved_match_team_count"] == 1
    assert result["summary"]["unresolved_series_team_count"] == 1
    assert result["summary"]["unresolved_series_source_token_count"] == 1
    assert result["placeholder_mappings"][0]["team_name"] == "Tuamanji"
    assert result["unresolved_match_teams"][0]["team_name"] == "Ghost Team"
    assert result["unresolved_series_teams"][0]["team_name"] == "Ghost Team"
    assert result["unresolved_series_source_tokens"][0]["source_token"] == "mfl o 200"
    assert result["seasons"][0]["season"] == 2023


def test_get_history_owner_gap_report_denies_other_league_access(db_session):
    league_a = make_league(db_session)
    league_b = make_league(db_session)

    user_a = make_user(db_session, league_a, "gap-owner-a", "Team A")
    make_user(db_session, league_b, "gap-owner-b", "Team B")

    with pytest.raises(HTTPException) as exc:
        get_history_owner_gap_report(league_id=league_b.id, db=db_session, current_user=user_a)

    assert exc.value.status_code == 403


def test_get_history_owner_gap_report_returns_empty_summary_without_history_rows(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "gap-empty", "Gap Empty Team")

    result = get_history_owner_gap_report(league_id=league.id, db=db_session, current_user=current_user)

    assert result["league_id"] == league.id
    assert result["summary"] == {
        "placeholder_mapping_count": 0,
        "unresolved_match_team_count": 0,
        "unresolved_series_team_count": 0,
        "unresolved_series_source_token_count": 0,
        "season_count": 0,
    }
    assert result["seasons"] == []
    assert result["placeholder_mappings"] == []
    assert result["unresolved_match_teams"] == []
    assert result["unresolved_series_teams"] == []
    assert result["unresolved_series_source_tokens"] == []


def test_get_history_owner_gap_report_ignores_malformed_record_json_rows(db_session, caplog):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "gap-malformed", "Gap Malformed Team")

    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_matchup_records_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="owner-gap-malformed-match-1",
            record_json="bad-match-payload",
        )
    )
    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_all_time_series_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="owner-gap-malformed-series-1",
            record_json=["bad", "series", "payload"],
        )
    )
    db_session.commit()

    with caplog.at_level(logging.WARNING, logger="backend.routers.league"):
        result = get_history_owner_gap_report(league_id=league.id, db=db_session, current_user=current_user)

    assert result["summary"] == {
        "placeholder_mapping_count": 0,
        "unresolved_match_team_count": 0,
        "unresolved_series_team_count": 0,
        "unresolved_series_source_token_count": 0,
        "season_count": 0,
    }
    assert result["seasons"] == []
    assert result["metadata"]["ignored_malformed_row_count"] == {
        "match_records": 1,
        "series_records": 1,
    }
    assert any("history owner gap report ignored malformed rows" in record.message for record in caplog.records)


def test_get_history_owner_gap_report_applies_detail_and_season_limits(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "gap-limited", "Gap Limited Team")

    db_session.add_all(
        [
            models.MflHtmlRecordFact(
                dataset_key="html_matchup_records_normalized",
                season=2026,
                target_league_id=league.id,
                league_id=str(league.id),
                normalization_version="v1",
                row_fingerprint="owner-gap-limit-match-1",
                record_json={
                    "record_year": 2023,
                    "record_week": 1,
                    "away_franchise_raw": "Ghost Team A",
                    "away_points": 100.0,
                    "home_franchise_raw": "Home Team A",
                    "home_points": 90.0,
                    "combined_score": 190.0,
                },
            ),
            models.MflHtmlRecordFact(
                dataset_key="html_matchup_records_normalized",
                season=2026,
                target_league_id=league.id,
                league_id=str(league.id),
                normalization_version="v1",
                row_fingerprint="owner-gap-limit-match-2",
                record_json={
                    "record_year": 2024,
                    "record_week": 2,
                    "away_franchise_raw": "Ghost Team B",
                    "away_points": 102.0,
                    "home_franchise_raw": "Home Team B",
                    "home_points": 92.0,
                    "combined_score": 194.0,
                },
            ),
        ]
    )
    db_session.commit()

    result = get_history_owner_gap_report(
        league_id=league.id,
        detail_limit=1,
        season_limit=1,
        db=db_session,
        current_user=current_user,
    )

    assert result["summary"]["unresolved_match_team_count"] >= 2
    assert len(result["unresolved_match_teams"]) == 1
    assert len(result["seasons"]) == 1
    assert result["metadata"]["response_limits"] == {
        "detail_limit": 1,
        "season_limit": 1,
    }
    assert result["metadata"]["truncated"]["unresolved_match_teams"] is True
    assert result["metadata"]["truncated"]["seasons"] is True


def test_ask_history_question_champion(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "champ-reader", "Champ Team")

    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_league_champions_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="champ-record-1",
            record_json={
                "record_year": 2021,
                "owner_name": "Champion Charlie",
            },
        )
    )
    db_session.commit()

    response = ask_history_question(
        league_id=league.id,
        payload=HistoryQuestionRequest(question="who won in 2021?"),
        db=db_session,
        current_user=current_user,
    )
    assert response["intent"] == "champion-lookup"
    assert "Champion Charlie" in response["answer"]


def test_ask_history_question_highest_scoring_game(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "game-reader", "Game Team")

    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_matchup_records_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="matchup-record-1",
            record_json={
                "record_year": 2019,
                "record_week": 7,
                "home_team": "Fire Hawks",
                "away_team": "Storm Riders",
                "combined_score": 310.5,
            },
        )
    )
    db_session.commit()

    response = ask_history_question(
        league_id=league.id,
        payload=HistoryQuestionRequest(question="what was the highest scoring game in 2019?"),
        db=db_session,
        current_user=current_user,
    )
    assert response["intent"] == "highest-scoring-matchup"
    assert "310" in response["answer"]


def test_ask_history_question_most_wins(db_session):
    league = make_league(db_session)
    current_user = make_user(db_session, league, "wins-reader", "Wins Team")

    db_session.add(
        models.MflHtmlRecordFact(
            dataset_key="html_season_records_normalized",
            season=2026,
            target_league_id=league.id,
            league_id=str(league.id),
            normalization_version="v1",
            row_fingerprint="season-record-1",
            record_json={
                "record_year": 2022,
                "owner_name": "Dominant Dave",
                "wins": 13,
            },
        )
    )
    db_session.commit()

    response = ask_history_question(
        league_id=league.id,
        payload=HistoryQuestionRequest(question="who had the most wins in 2022?"),
        db=db_session,
        current_user=current_user,
    )
    assert response["intent"] == "season-most-wins"
    assert "Dominant Dave" in response["answer"]
