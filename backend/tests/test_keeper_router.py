import sys
from pathlib import Path
from datetime import UTC, datetime, timedelta
import io

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import UploadFile

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.routers.keepers import (
    get_my_keepers,
    save_my_keepers,
    lock_my_keepers,
    remove_keeper,
    get_keeper_settings,
    update_keeper_settings,
    list_all_keepers,
    veto_owner_list,
    reset_league_keepers,
    commissioner_override_keeper,
    import_keeper_history_csv,
    import_economic_history_csv,
    download_keeper_history_template,
    download_economic_history_template,
    KeeperOverrideRequest,
    KeeperSelectionSchema,
    KeeperSettingsUpdate,
)
from fastapi import HTTPException


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def make_league(db, name="L"):
    l = models.League(name=name)
    db.add(l)
    db.commit()
    db.refresh(l)
    # also add league settings
    ls = models.LeagueSettings(league_id=l.id, draft_year=2026)
    db.add(ls)
    db.commit()
    return l


def make_player(db, name="P"):
    p = models.Player(name=name, position="RB", nfl_team="ABC")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def make_user(db, league, username="u", is_comm=False, budget=0):
    u = models.User(username=username, hashed_password="pw", league_id=league.id, future_draft_budget=budget)
    u.is_commissioner = is_comm
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


class CU:
    def __init__(self, user):
        self.id = user.id
        self.league_id = user.league_id
        self.future_draft_budget = user.future_draft_budget
        self.is_commissioner = user.is_commissioner
        self.username = user.username
        self.team_name = getattr(user, 'team_name', None)


def test_owner_keeper_endpoints():
    db_session = setup_db()
    league = make_league(db_session)
    # ensure keeper rules exist so max_allowed reflects expected value
    db_session.add(models.KeeperRules(league_id=league.id, max_keepers=3))
    db_session.commit()
    owner = make_user(db_session, league, "owner", budget=200)
    p1 = make_player(db_session, "A")
    p2 = make_player(db_session, "B")

    current = CU(owner)
    # initial get should return empty selections
    resp = get_my_keepers(db=db_session, current_user=current)
    assert resp.selected_count == 0
    assert resp.max_allowed == 3
    assert resp.estimated_budget == 200

    # save two keepers
    req = type("R", (), {})()
    req.players = [KeeperSelectionSchema(player_id=p1.id, keep_cost=10, years_kept_count=0, status="pending", approved_by_commish=False),
                   KeeperSelectionSchema(player_id=p2.id, keep_cost=20, years_kept_count=0, status="pending", approved_by_commish=False)]
    save_my_keepers(request=req, db=db_session, current_user=current)
    resp2 = get_my_keepers(db=db_session, current_user=current)
    assert resp2.selected_count == 2
    assert resp2.estimated_budget == 170

    # lock them and verify budget deduction
    # pass the actual owner object (models.User) rather than CU stub
    lock_my_keepers(db=db_session, current_user=db_session.get(models.User, owner.id))
    # use new SQLAlchemy 2.0 style get
    owner_ref = db_session.get(models.User, owner.id)
    assert owner_ref.future_draft_budget == 170
    # after lock, effective budget matches
    resp3 = get_my_keepers(db=db_session, current_user=current)
    assert resp3.effective_budget == 170

    # remove keeper should do nothing because list locked
    remove_keeper(player_id=p1.id, db=db_session, current_user=current)
    resp4 = get_my_keepers(db=db_session, current_user=current)
    assert resp4.selected_count == 2


def test_admin_settings_and_actions():
    db_session = setup_db()
    league = make_league(db_session)
    comm = make_user(db_session, league, "comm", is_comm=True)
    other = make_user(db_session, league, "owner2")
    current_comm = CU(comm)

    # update settings - use real Pydantic schema so `.model_dump()` works
    # KeeperSettingsUpdate is defined inside the router module
    from backend.routers.keepers import KeeperSettingsUpdate

    upd = KeeperSettingsUpdate(
        max_keepers=2,
        max_years_per_player=2,
        deadline_date=datetime.now(UTC) + timedelta(days=1),
        waiver_policy=True,
        trade_deadline=None,
        drafted_only=True,
        cost_type="round",
        cost_inflation=5,
    )

    update_keeper_settings(update=upd, db=db_session, current_user=current_comm)
    outs = get_keeper_settings(db=db_session, current_user=current_comm)
    assert outs.max_keepers == 2
    assert outs.cost_type == "round"
    assert outs.cost_inflation == 5

    # save some keepers for both owners
    p = make_player(db_session, "X")
    req1 = type("R", (), {})()
    req1.players = [KeeperSelectionSchema(player_id=p.id, keep_cost=5, years_kept_count=0, status="pending", approved_by_commish=False)]
    save_my_keepers(request=req1, db=db_session, current_user=CU(other))
    # list all for commissioner
    all_lists = list_all_keepers(db=db_session, current_user=current_comm)
    assert len(all_lists) == 1

    # lock owner's list and then veto via admin
    lock_my_keepers(db=db_session, current_user=db_session.get(models.User, other.id))
    veto_owner_list(owner_id=other.id, db=db_session, current_user=current_comm)
    post = get_my_keepers(db=db_session, current_user=CU(other))
    assert post.selected_count == 1  # still present but status pending again

    # reset league
    reset_league_keepers(owner_id=None, db=db_session, current_user=current_comm)
    post2 = get_my_keepers(db=db_session, current_user=CU(other))
    assert post2.selected_count == 0


def test_keeper_settings_propagate_to_owner_page_and_lock_enforcement():
    db_session = setup_db()
    league = make_league(db_session)
    comm = make_user(db_session, league, "comm-prop", is_comm=True)
    owner = make_user(db_session, league, "owner-prop", budget=200)
    current_comm = CU(comm)

    p1 = make_player(db_session, "K1")
    p2 = make_player(db_session, "K2")

    # Owner has draft picks available for keeper selection.
    db_session.add_all(
        [
            models.DraftPick(owner_id=owner.id, player_id=p1.id, league_id=league.id, amount=10),
            models.DraftPick(owner_id=owner.id, player_id=p2.id, league_id=league.id, amount=12),
        ]
    )
    db_session.commit()

    # Seed baseline keeper rules and verify owner page reflects them.
    db_session.add(
        models.KeeperRules(
            league_id=league.id,
            max_keepers=1,
            max_years_per_player=2,
            deadline_date=datetime.now(UTC) + timedelta(days=2),
            waiver_policy=False,
            drafted_only=False,
            cost_type="auction",
            cost_inflation=0,
        )
    )
    db_session.commit()

    owner_view_before = get_my_keepers(db=db_session, current_user=CU(owner))
    assert owner_view_before.max_allowed == 1

    # Commissioner overwrites non-scoring keeper settings.
    update_keeper_settings(
        update=KeeperSettingsUpdate(
            max_keepers=2,
            max_years_per_player=3,
            deadline_date=datetime.now(UTC) + timedelta(days=1),
            waiver_policy=True,
            drafted_only=True,
            cost_type="round",
            cost_inflation=5,
        ),
        db=db_session,
        current_user=current_comm,
    )

    owner_view_after = get_my_keepers(db=db_session, current_user=CU(owner))
    assert owner_view_after.max_allowed == 2

    # Save a keeper and ensure lock works before deadline.
    req = type("R", (), {})()
    req.players = [
        KeeperSelectionSchema(
            player_id=p1.id,
            keep_cost=10,
            years_kept_count=0,
            status="pending",
            approved_by_commish=False,
        )
    ]
    save_my_keepers(request=req, db=db_session, current_user=CU(owner))
    lock_my_keepers(db=db_session, current_user=db_session.get(models.User, owner.id))

    # Commissioner overwrites deadline to the past; next lock attempt must fail.
    update_keeper_settings(
        update=KeeperSettingsUpdate(deadline_date=datetime.now(UTC) - timedelta(minutes=1)),
        db=db_session,
        current_user=current_comm,
    )

    remove_keeper(player_id=p1.id, db=db_session, current_user=CU(owner))
    save_my_keepers(request=req, db=db_session, current_user=CU(owner))

    with pytest.raises(HTTPException, match="Keeper window has closed"):
        lock_my_keepers(db=db_session, current_user=db_session.get(models.User, owner.id))


def test_update_keeper_settings_rejects_invalid_values():
    db_session = setup_db()
    league = make_league(db_session)
    comm = make_user(db_session, league, "comm-invalid", is_comm=True)
    current_comm = CU(comm)

    from backend.routers.keepers import KeeperSettingsUpdate

    invalid = KeeperSettingsUpdate(
        max_keepers=50,
        cost_type="bad_type",
    )

    with pytest.raises(HTTPException) as exc:
        update_keeper_settings(update=invalid, db=db_session, current_user=current_comm)

    assert exc.value.status_code == 400


def test_commissioner_override_supersedes_owner_submission():
    db_session = setup_db()
    league = make_league(db_session)
    comm = make_user(db_session, league, "comm", is_comm=True)
    owner = make_user(db_session, league, "owner")
    player = make_player(db_session, "Override Target")

    # commissioner manually overrides keeper
    commissioner_override_keeper(
        request=KeeperOverrideRequest(
            owner_id=owner.id,
            player_name=player.name,
            nfl_team=player.nfl_team,
            keep_cost=12,
            years_kept_count=2,
        ),
        db=db_session,
        current_user=CU(comm),
    )

    # owner submits empty keepers list; override should remain selected
    req = type("R", (), {})()
    req.players = []
    save_my_keepers(request=req, db=db_session, current_user=CU(owner))

    resp = get_my_keepers(db=db_session, current_user=CU(owner))
    assert resp.selected_count == 1
    assert any(s.player_id == player.id for s in resp.selections)


def test_keeper_rollover_locks_prior_pending_and_opens_new_slots():
    db_session = setup_db()
    league = make_league(db_session)
    owner = make_user(db_session, league, "owner-rollover", budget=200)
    p = make_player(db_session, "Season Bridge")

    # Create a stale prior-season pending keeper that should auto-lock on rollover.
    db_session.add(
        models.Keeper(
            league_id=league.id,
            owner_id=owner.id,
            player_id=p.id,
            season=2026,
            keep_cost=10,
            status="pending",
        )
    )
    settings = (
        db_session.query(models.LeagueSettings)
        .filter(models.LeagueSettings.league_id == league.id)
        .first()
    )
    settings.draft_year = 2027
    db_session.commit()

    resp = get_my_keepers(db=db_session, current_user=CU(owner))
    assert resp.selected_count == 0

    previous_season_keeper = (
        db_session.query(models.Keeper)
        .filter(
            models.Keeper.owner_id == owner.id,
            models.Keeper.player_id == p.id,
            models.Keeper.season == 2026,
        )
        .first()
    )
    assert previous_season_keeper is not None
    assert previous_season_keeper.status == "locked"
    assert previous_season_keeper.locked_at is not None


@pytest.mark.asyncio
async def test_keeper_history_csv_import_and_template():
    db_session = setup_db()
    league = make_league(db_session)
    comm = make_user(db_session, league, "comm", is_comm=True)
    owner = make_user(db_session, league, "alice")
    owner.team_name = "Team Alice"
    db_session.commit()

    player = models.Player(
        name="Justin Jefferson",
        position="WR",
        nfl_team="MIN",
        gsis_id="00-0036322",
    )
    db_session.add(player)
    db_session.commit()

    template = download_keeper_history_template(current_user=CU(comm))
    assert "season,owner_username,owner_team_name,player_name" in template

    csv_text = (
        "season,owner_username,owner_team_name,player_name,nfl_team,gsis_id,keep_cost,years_kept_count,status\n"
        "2026,alice,Team Alice,Justin Jefferson,MIN,00-0036322,25,2,historical_import\n"
    )
    upload = UploadFile(filename="keepers.csv", file=io.BytesIO(csv_text.encode("utf-8")))

    dry_run_result = await import_keeper_history_csv(
        file=upload,
        dry_run=True,
        db=db_session,
        current_user=CU(comm),
    )
    assert dry_run_result.inserted == 1
    assert db_session.query(models.Keeper).count() == 0

    upload_real = UploadFile(filename="keepers.csv", file=io.BytesIO(csv_text.encode("utf-8")))
    write_result = await import_keeper_history_csv(
        file=upload_real,
        dry_run=False,
        db=db_session,
        current_user=CU(comm),
    )
    assert write_result.inserted == 1
    inserted = db_session.query(models.Keeper).first()
    assert inserted is not None
    assert inserted.owner_id == owner.id
    assert inserted.player_id == player.id
    assert inserted.status == "historical_import"


@pytest.mark.asyncio
async def test_economic_history_csv_import_and_template():
    db_session = setup_db()
    league = make_league(db_session)
    comm = make_user(db_session, league, "comm", is_comm=True)
    owner_a = make_user(db_session, league, "alice")
    owner_b = make_user(db_session, league, "bob")
    owner_a.team_name = "Team Alice"
    owner_b.team_name = "Team Bob"
    db_session.commit()

    template = download_economic_history_template(current_user=CU(comm))
    assert "season,entry_type,owner_username,owner_team_name" in template

    csv_text = (
        "season,entry_type,owner_username,owner_team_name,from_owner_username,to_owner_username,amount,currency_type,note,reference_id\n"
        "2026,STARTING_BUDGET,alice,Team Alice,,,210,DRAFT_DOLLARS,Initial budget,budget-2026-alice\n"
        "2026,TRADE,,,alice,bob,15,DRAFT_DOLLARS,Trade adjustment,trade-2026-a-b\n"
        "2026,AWARD,bob,Team Bob,,,10,DRAFT_DOLLARS,Bonus,award-2026-bob\n"
    )
    upload_dry = UploadFile(filename="economic.csv", file=io.BytesIO(csv_text.encode("utf-8")))

    dry_result = await import_economic_history_csv(
        file=upload_dry,
        dry_run=True,
        db=db_session,
        current_user=CU(comm),
    )
    assert dry_result.inserted == 3
    assert db_session.query(models.EconomicLedger).count() == 0
    assert db_session.query(models.DraftBudget).count() == 0

    upload_real = UploadFile(filename="economic.csv", file=io.BytesIO(csv_text.encode("utf-8")))
    write_result = await import_economic_history_csv(
        file=upload_real,
        dry_run=False,
        db=db_session,
        current_user=CU(comm),
    )
    assert write_result.inserted == 3
    assert db_session.query(models.EconomicLedger).count() == 3

    budget = (
        db_session.query(models.DraftBudget)
        .filter(
            models.DraftBudget.league_id == league.id,
            models.DraftBudget.owner_id == owner_a.id,
            models.DraftBudget.year == 2026,
        )
        .first()
    )
    assert budget is not None
    assert int(budget.total_budget) == 210
