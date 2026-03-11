import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from fastapi import HTTPException
from backend.routers.league import get_league_budgets, get_league_settings, update_league_budgets, BudgetUpdateRequest, BudgetEntry, get_ledger_statement, LeagueConfigFull, ScoringRuleSchema, validate_lineup_rules
from backend.routers.draft import _get_owner_total_budget


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
    l = models.League(name="L")
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

    result = get_league_budgets(league_id=league.id, year=2026, db=db_session)
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

    result = get_league_budgets(league_id=league.id, year=2026, db=db_session)
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

    result = get_league_budgets(league_id=league.id, year=2027, db=db_session)
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

    budgets = get_league_budgets(league_id=league.id, year=2028, db=db_session)
    budget_map = {r["owner_id"]: r["total_budget"] for r in budgets}
    assert budget_map[u1.id] == 210
    assert budget_map[u2.id] == 190


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


def test_get_ledger_statement_owner_self(db_session):
    league = make_league(db_session)
    owner = make_user(db_session, league, "ledger-self", "TeamSelf")
    other = make_user(db_session, league, "ledger-other", "TeamOther")

    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=2030,
            currency_type="DRAFT_DOLLARS",
            amount=200,
            from_owner_id=None,
            to_owner_id=owner.id,
            transaction_type="SEASON_ALLOCATION",
            reference_type="LEAGUE_BUDGETS",
            reference_id=f"{league.id}:2030:{owner.id}",
        )
    )
    db_session.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=2030,
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
        season_year=2030,
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
            season_year=2031,
            currency_type="FAAB",
            amount=100,
            from_owner_id=None,
            to_owner_id=owner.id,
            transaction_type="SEASON_ALLOCATION",
            reference_type="LEAGUE_SETTINGS",
            reference_id=f"{league.id}:2031:faab",
        )
    )
    db_session.commit()

    statement = get_ledger_statement(
        league_id=league.id,
        owner_id=owner.id,
        currency_type="FAAB",
        season_year=2031,
        limit=25,
        current_user=comm,
        db=db_session,
    )
    assert statement.owner_id == owner.id
    assert statement.balance == 100
    assert statement.entry_count == 1
    assert statement.entries[0].direction == "CREDIT"
