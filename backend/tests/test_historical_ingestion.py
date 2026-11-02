import pytest
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import models
from backend.core import security
from backend.routers.draft import _get_websocket_user
from backend.routers.league import fetch_league_owners_data
from backend.scripts import audit_player_duplicates
from backend.services.player_service import find_existing_player
from backend.services.waiver_service import process_claim
from backend.uat import seed_players


@pytest.fixture
def history_db():
    engine = create_engine("sqlite://")
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.mark.parametrize("provider", ["mfl_id", "sleeper_id"])
def test_provider_identity_precedes_changed_name_and_team(history_db, provider):
    player = models.Player(
        name="Original", position="WR", nfl_team="FA", **{provider: "00123"}
    )
    history_db.add(player)
    history_db.commit()
    assert (
        find_existing_player(
            history_db,
            **{provider: "00123"},
            name="Changed",
            position="TE",
            nfl_team="BUF"
        )
        is player
    )
    assert getattr(player, provider) == "00123"


def test_provider_conflicts_and_ambiguous_names_fail_closed(history_db):
    first = models.Player(name="Same", position="WR", nfl_team="BUF", mfl_id="001")
    second = models.Player(name="Same", position="WR", nfl_team="BUF", sleeper_id="002")
    history_db.add_all([first, second])
    history_db.commit()
    with pytest.raises(ValueError, match="different canonical players"):
        find_existing_player(history_db, mfl_id="001", sleeper_id="002")
    with pytest.raises(ValueError, match="conflicts"):
        find_existing_player(
            history_db, mfl_id="003", name="Same", position="WR", nfl_team="BUF"
        )
    first.mfl_id = None
    history_db.commit()
    with pytest.raises(ValueError, match="Ambiguous"):
        find_existing_player(
            history_db, mfl_id="003", name="Same", position="WR", nfl_team="BUF"
        )


@pytest.mark.parametrize(
    "model,identifier",
    [
        (models.DraftPick, "source_event_id"),
        (models.TransactionHistory, "source_transaction_id"),
    ],
)
def test_source_event_identity_preserves_distinct_observations(
    history_db, model, identifier
):
    history_db.add_all(
        [models.League(id=1, name="one"), models.League(id=2, name="two")]
    )
    player = models.Player(name="Player", position="WR", nfl_team="BUF")
    history_db.add(player)
    history_db.flush()
    extra = (
        {"player_id": player.id, "transaction_type": "draft"}
        if model is models.TransactionHistory
        else {}
    )
    for league, source, event in [
        (1, "mfl", "one"),
        (1, "mfl", "two"),
        (1, "other", "one"),
        (2, "mfl", "one"),
    ]:
        history_db.add(
            model(league_id=league, source=source, **{identifier: event}, **extra)
        )
    history_db.add_all([model(league_id=1, **extra), model(league_id=1, **extra)])
    history_db.commit()
    assert history_db.query(model).count() == 6
    history_db.add(model(league_id=1, source="mfl", **{identifier: "one"}, **extra))
    with pytest.raises(IntegrityError):
        history_db.commit()
    history_db.rollback()
    assert history_db.query(model).count() == 6


@pytest.mark.parametrize(
    "source,league,event",
    [(None, 1, "one"), (" ", 1, "one"), ("mfl", None, "one"), ("mfl", 1, "")],
)
def test_event_key_requires_complete_source_scope(history_db, source, league, event):
    history_db.add(
        models.DraftPick(league_id=league, source=source, source_event_id=event)
    )
    with pytest.raises(IntegrityError):
        history_db.commit()


def test_waiver_budget_and_ledger_use_only_active_season(history_db):
    league = models.League(name="Seasonal", current_season=2030)
    history_db.add(league)
    history_db.flush()
    user = models.User(username="owner", league_id=league.id)
    target = models.Player(name="Target", position="RB", nfl_team="BUF")
    history_db.add_all([user, target])
    history_db.flush()
    budgets = [
        models.WaiverBudget(
            league_id=league.id,
            owner_id=user.id,
            year=2029,
            starting_budget=100,
            remaining_budget=1,
        ),
        models.WaiverBudget(
            league_id=league.id,
            owner_id=user.id,
            year=2030,
            starting_budget=100,
            remaining_budget=40,
            spent_budget=60,
        ),
    ]
    history_db.add_all(budgets)
    history_db.add(
        models.EconomicLedger(
            league_id=league.id,
            season_year=2029,
            currency_type="FAAB",
            amount=1000,
            to_owner_id=user.id,
            transaction_type="OLD_CREDIT",
        )
    )
    history_db.commit()
    pick = process_claim(history_db, user, target.id, 12)
    assert pick.year == 2030
    assert budgets[0].remaining_budget == 1
    assert budgets[1].remaining_budget == 28
    assert budgets[1].spent_budget == 72
    debit = history_db.query(models.EconomicLedger).filter_by(season_year=2030).one()
    assert debit.amount == 12


def test_provider_bound_duplicates_are_reported_but_never_auto_merged(
    history_db, monkeypatch
):
    engine = history_db.get_bind()
    history_db.add_all(
        [
            models.Player(name="Same", position="WR", nfl_team="BUF", mfl_id="001"),
            models.Player(name="Same", position="WR", nfl_team="BUF", mfl_id="002"),
        ]
    )
    history_db.commit()
    monkeypatch.setattr(
        audit_player_duplicates, "SessionLocal", lambda: Session(engine)
    )
    report = audit_player_duplicates.run_audit()
    assert report["provider_bound_groups"] == 1
    assert report["groups"][0]["provider_conflicts"] == ["mfl_id"]
    with pytest.raises(ValueError, match="reviewed canonical mappings"):
        audit_player_duplicates.run_audit(apply_changes=True)
    assert history_db.query(models.Player).count() == 2


def test_sleeper_loader_binds_native_id_without_misusing_gsis(history_db, monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "001": {
                    "active": True,
                    "position": "WR",
                    "full_name": "Receiver",
                    "team": "BUF",
                    "gsis_id": "00-123",
                }
            }

    calls = []

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr(seed_players.requests, "get", get)
    seed_players.seed_players(history_db)
    seed_players.seed_players(history_db)
    player = history_db.query(models.Player).one()
    assert player.sleeper_id == "001"
    assert player.gsis_id == "00-123"
    assert len(calls) == 2


def test_active_membership_and_websocket_auth_both_exclude_archival_accounts(
    history_db,
):
    league = models.League(name="Account isolation")
    history_db.add(league)
    history_db.flush()
    users = [
        models.User(username="active", league_id=league.id),
        models.User(username="renamed", league_id=league.id, is_historical_stub=True),
        models.User(username="hist_2020_0001", league_id=league.id),
    ]
    history_db.add_all(users)
    history_db.commit()
    assert [
        row["username"] for row in fetch_league_owners_data(league.id, history_db)
    ] == ["active"]
    for user in users:
        socket = SimpleNamespace(
            cookies={
                security.ACCESS_TOKEN_COOKIE_NAME: security.create_access_token(
                    {"sub": user.username}
                )
            },
            query_params={},
        )
        actual = _get_websocket_user(socket, history_db)
        assert actual is (users[0] if user is users[0] else None)
