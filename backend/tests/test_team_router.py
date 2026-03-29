import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException, status

# `client` fixture provided by backend/conftest; it avoids running the
# application's lifespan on every test.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.database import get_db
from backend.main import app


@pytest.fixture
def api_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db, TestingSessionLocal
    finally:
        db.close()


# dependency override is handled automatically for all tests that need the
# in-memory `api_db` fixture.  we declare this hook once and let todos use
# the plain `client` fixture from conftest.
@pytest.fixture(autouse=True)
def override_db(api_db):
    db, _ = api_db
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def test_view_empty_team_returns_200(client, api_db):
    db, _ = api_db
    # create a user with no picks
    user = models.User(username='user1',
                       email='u1@test.com',
                       hashed_password='hashed',
                       is_commissioner=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    res = client.get(f'/team/{user.id}?week=1')
    assert res.status_code == 200
    body = res.json()
    assert body['owner_id'] == user.id
    assert isinstance(body.get('players'), list)
    assert body['players'] == []


def test_team_500_before_model_wouldhave_failed():
    # simply ensure the LineupSubmission class exists on startup
    assert hasattr(models, 'LineupSubmission'), "LineupSubmission model must exist"


# --- validation helper tests (no HTTP requests required) ---

def _make_pick(position):
    # simple object imitating a DraftPick with a .player.position attribute
    class Dummy:
        def __init__(self, pos):
            self.player = type("P", (), {"position": pos})

    return Dummy(position)


def test_validate_lineup_requirements_flex_correct():
    # one of each base position plus one extra RB to satisfy a FLEX slot
    settings = models.LeagueSettings(
        league_id=1,
        starting_slots={
            "QB": 1,
            "RB": 1,
            "WR": 1,
            "TE": 1,
            "K": 0,
            "DEF": 0,
            "FLEX": 1,
            "ACTIVE_ROSTER_SIZE": 5,
        },
    )
    starters = [
        _make_pick("QB"),
        _make_pick("RB"),
        _make_pick("WR"),
        _make_pick("TE"),
        _make_pick("RB"),
    ]
    errors = models.validate_lineup_requirements(starters, settings) if hasattr(models, 'validate_lineup_requirements') else None
    # we imported the function directly below to avoid circular import
    from backend.routers.team import validate_lineup_requirements
    errors = validate_lineup_requirements(starters, settings)
    assert errors == []


def test_validate_lineup_requirements_flex_not_enough():
    settings = models.LeagueSettings(
        league_id=2,
        starting_slots={
            "QB": 1,
            "RB": 1,
            "WR": 1,
            "TE": 1,
            "K": 0,
            "DEF": 0,
            "FLEX": 1,
            "ACTIVE_ROSTER_SIZE": 5,
        },
    )
    # only the four base players, flex slot empty
    starters = [
        _make_pick("QB"),
        _make_pick("RB"),
        _make_pick("WR"),
        _make_pick("TE"),
    ]
    from backend.routers.team import validate_lineup_requirements
    errors = validate_lineup_requirements(starters, settings)
    assert "not enough FLEX (needs extra RB/WR/TE starter)" in errors


def test_validate_lineup_requirements_flex_too_many():
    settings = models.LeagueSettings(
        league_id=3,
        starting_slots={
            "QB": 1,
            "RB": 1,
            "WR": 1,
            "TE": 1,
            "K": 0,
            "DEF": 0,
            "FLEX": 1,
            "ACTIVE_ROSTER_SIZE": 5,
        },
    )
    # supply too many flex-eligible players
    starters = [
        _make_pick("QB"),
        _make_pick("RB"),
        _make_pick("WR"),
        _make_pick("TE"),
        _make_pick("WR"),
        _make_pick("RB"),
    ]
    from backend.routers.team import validate_lineup_requirements
    errors = validate_lineup_requirements(starters, settings)
    # should complain about too many players; flex-specific error may also appear
    assert "too many players" in errors
    assert (
        "too many FLEX-eligible starters (RB/WR/TE)" in errors
        or "too many players" in errors
    )

def test_validate_lineup_requirements_two_flex_slots():
    # verify algorithm works when there are multiple FLEX positions
    settings = models.LeagueSettings(
        league_id=4,
        starting_slots={
            "QB": 1,
            "RB": 1,
            "WR": 1,
            "TE": 1,
            "K": 0,
            "DEF": 0,
            "FLEX": 2,
            "ACTIVE_ROSTER_SIZE": 6,
        },
    )
    starters = [
        _make_pick("QB"),
        _make_pick("RB"),
        _make_pick("WR"),
        _make_pick("TE"),
        _make_pick("RB"),
        _make_pick("WR"),
    ]
    from backend.routers.team import validate_lineup_requirements
    errors = validate_lineup_requirements(starters, settings)
    assert errors == []


def test_validate_lineup_requirements_caps_invalid_minimums_at_configured_maximums():
    settings = models.LeagueSettings(
        league_id=40,
        starting_slots={
            "QB": 1,
            "RB": 5,
            "WR": 2,
            "TE": 1,
            "K": 0,
            "DEF": 0,
            "FLEX": 1,
            "ACTIVE_ROSTER_SIZE": 9,
            "MAX_QB": 3,
            "MAX_RB": 4,
            "MAX_WR": 3,
            "MAX_TE": 2,
            "MAX_K": 0,
            "MAX_DEF": 1,
            "MAX_FLEX": 1,
        },
    )
    starters = [
        _make_pick("QB"),
        _make_pick("RB"),
        _make_pick("RB"),
        _make_pick("RB"),
        _make_pick("RB"),
        _make_pick("WR"),
        _make_pick("WR"),
        _make_pick("TE"),
        _make_pick("DEF"),
    ]
    from backend.routers.team import validate_lineup_requirements

    errors = validate_lineup_requirements(starters, settings)
    assert errors == []


def test_validate_lineup_requirements_ignores_stale_hidden_minimums():
    settings = models.LeagueSettings(
        league_id=41,
        starting_slots={
            "QB": 2,
            "RB": 4,
            "WR": 2,
            "TE": 0,
            "K": 1,
            "DEF": 1,
            "FLEX": 1,
            "ACTIVE_ROSTER_SIZE": 8,
            "MAX_QB": 2,
            "MAX_RB": 4,
            "MAX_WR": 5,
            "MAX_TE": 3,
            "MAX_K": 0,
            "MAX_DEF": 1,
            "MAX_FLEX": 1,
        },
    )
    starters = [
        _make_pick("QB"),
        _make_pick("RB"),
        _make_pick("RB"),
        _make_pick("RB"),
        _make_pick("WR"),
        _make_pick("WR"),
        _make_pick("TE"),
        _make_pick("DEF"),
    ]
    from backend.routers.team import validate_lineup_requirements

    errors = validate_lineup_requirements(starters, settings)
    assert errors == []


def test_validate_lineup_requirements_allows_under_minimum_slots_when_partial_enabled():
    settings = models.LeagueSettings(
        league_id=42,
        starting_slots={
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "K": 0,
            "DEF": 1,
            "FLEX": 1,
            "ACTIVE_ROSTER_SIZE": 8,
            "MAX_QB": 1,
            "MAX_RB": 3,
            "MAX_WR": 3,
            "MAX_TE": 1,
            "MAX_K": 0,
            "MAX_DEF": 1,
            "MAX_FLEX": 1,
            "ALLOW_PARTIAL_LINEUP": 1,
        },
    )
    starters = [
        _make_pick("QB"),
        _make_pick("RB"),
        _make_pick("WR"),
        _make_pick("TE"),
        _make_pick("DEF"),
    ]
    from backend.routers.team import validate_lineup_requirements

    errors = validate_lineup_requirements(starters, settings)
    assert errors == []




def test_validate_lineup_skips_taxi():
    # a pick marked as taxi should not be counted as a starter
    class FakePick:
        def __init__(self, pos, is_taxi=False):
            self.player = type("P", (), {"position": pos})
            self.is_taxi = is_taxi
    settings = models.LeagueSettings(
        league_id=5,
        starting_slots={"QB":1, "RB":1, "WR":1, "TE":1, "K":0, "DEF":0, "FLEX":0, "ACTIVE_ROSTER_SIZE":4},
    )
    starters = [FakePick('QB'), FakePick('RB'), FakePick('WR'), FakePick('TE', is_taxi=True)]
    from backend.routers.team import validate_lineup_requirements
    errs = validate_lineup_requirements(starters, settings)
    # only three non-taxi starters present, so validator should complain
    assert any('not enough' in e for e in errs)

# --- taxi squad behavior tests ---
def test_taxi_endpoints_and_validation(client, api_db):
    db, _ = api_db
    # create user and league
    from backend.core import security
    user = models.User(username='taxiuser',
                       email='taxi@test.com',
                       hashed_password=security.get_password_hash('hashed'))
    db.add(user)
    db.commit()
    db.refresh(user)
    league = models.League(name='TaxiLeague')
    db.add(league)
    db.commit()
    db.refresh(league)
    user.league_id = league.id
    db.commit()

    # create player and pick
    player = models.Player(name='Joe RB', position='RB', nfl_team='AAA')
    db.add(player)
    db.commit()
    db.refresh(player)
    pick = models.DraftPick(owner_id=user.id, player_id=player.id,
                             league_id=league.id, current_status='BENCH')
    db.add(pick)
    db.commit()
    db.refresh(pick)

    # bypass authentication by overriding the dependency to always return
    # our freshly-created user.  This avoids dealing with the test-hash value.
    from backend.core.security import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user
    # (no need to set Authorization header)

    # demote to taxi
    res = client.post('/team/taxi/demote', json={'player_id': player.id})
    assert res.status_code == 200
    assert res.json()['message'] == 'Player demoted to taxi'
    db.refresh(pick)
    assert pick.is_taxi

    # attempt lineup update with taxi player; update should succeed but
    # the later submission will fail because no starters remain (taxi excluded)
    upd = client.post('/team/lineup', json={'week':1,'starter_player_ids':[player.id]})
    assert upd.status_code == 200
    sub = client.post('/team/submit-lineup', json={'week':1})
    assert sub.status_code == 400
    assert "not enough" in sub.json().get('detail', [])[0]

    # promote back to bench so the same player can be started normally
    res = client.post('/team/taxi/promote', json={'player_id': player.id})
    assert res.status_code == 200
    assert res.json()['message'] == 'Player promoted from taxi'
    db.refresh(pick)
    assert not pick.is_taxi
    # now attempt update/submit with actual starter; still fails because league
    # settings require more players, but error should not mention taxi.
    upd2 = client.post('/team/lineup', json={'week':1,'starter_player_ids':[player.id]})
    assert upd2.status_code == 200
    sub2 = client.post('/team/submit-lineup', json={'week':1})
    assert sub2.status_code == 400
    assert "taxi" not in str(sub2.json().get('detail', ''))


def test_non_scoring_settings_update_propagates_to_lineup_submission(client, api_db):
    db, _ = api_db
    from backend.core import security
    from backend.core.security import get_current_user

    league = models.League(name='PropagationLeague')
    db.add(league)
    db.commit()
    db.refresh(league)

    commissioner = models.User(
        username='prop-commish',
        email='prop-commish@test.com',
        hashed_password=security.get_password_hash('pw'),
        league_id=league.id,
        is_commissioner=True,
    )
    db.add(commissioner)
    db.commit()
    db.refresh(commissioner)

    qb = models.Player(name='Prop QB', position='QB', nfl_team='AAA')
    rb = models.Player(name='Prop RB', position='RB', nfl_team='BBB')
    db.add_all([qb, rb])
    db.commit()
    db.refresh(qb)
    db.refresh(rb)

    current_year = datetime.now(timezone.utc).year
    db.add_all(
        [
            models.DraftPick(
                owner_id=commissioner.id,
                player_id=qb.id,
                league_id=league.id,
                current_status='STARTER',
                year=current_year,
            ),
            models.DraftPick(
                owner_id=commissioner.id,
                player_id=rb.id,
                league_id=league.id,
                current_status='BENCH',
                year=current_year,
            ),
        ]
    )
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: commissioner

    baseline_payload = {
        'roster_size': 14,
        'salary_cap': 200,
        'starting_slots': {
            'QB': 1,
            'RB': 2,
            'WR': 2,
            'TE': 1,
            'K': 0,
            'DEF': 1,
            'FLEX': 0,
            'ACTIVE_ROSTER_SIZE': 9,
            'MAX_QB': 2,
            'MAX_RB': 4,
            'MAX_WR': 5,
            'MAX_TE': 3,
            'MAX_K': 0,
            'MAX_DEF': 1,
            'MAX_FLEX': 0,
            'ALLOW_PARTIAL_LINEUP': 0,
            'REQUIRE_WEEKLY_SUBMIT': 1,
        },
        'waiver_deadline': 'Wed 11PM',
        'starting_waiver_budget': 100,
        'waiver_system': 'FAAB',
        'waiver_tiebreaker': 'standings',
        'trade_deadline': 'Fri 5PM',
        'draft_year': current_year,
        'scoring_rules': [
            {
                'category': 'passing',
                'event_name': 'passing_touchdown',
                'description': 'Passing TD',
                'point_value': 4,
                'calculation_type': 'flat_bonus',
                'applicable_positions': ['QB'],
            }
        ],
    }

    update_res = client.put(f'/leagues/{league.id}/settings', json=baseline_payload)
    assert update_res.status_code == 200

    blocked = client.post('/team/submit-lineup', json={'week': 1})
    assert blocked.status_code == status.HTTP_400_BAD_REQUEST
    assert any('not enough' in str(msg).lower() for msg in blocked.json().get('detail', []))

    baseline_payload['starting_slots']['ALLOW_PARTIAL_LINEUP'] = 1
    baseline_payload['waiver_deadline'] = 'Thu 10PM'
    baseline_payload['trade_deadline'] = 'Sat 3PM'

    update_partial_res = client.put(f'/leagues/{league.id}/settings', json=baseline_payload)
    assert update_partial_res.status_code == 200

    settings_res = client.get(f'/leagues/{league.id}/settings')
    assert settings_res.status_code == 200
    settings_body = settings_res.json()
    assert int(settings_body.get('starting_slots', {}).get('ALLOW_PARTIAL_LINEUP', 0)) == 1
    assert settings_body.get('waiver_deadline') == 'Thu 10PM'

    allowed = client.post('/team/submit-lineup', json={'week': 1})
    assert allowed.status_code == 200
    assert allowed.json().get('message') == 'Roster submitted'
