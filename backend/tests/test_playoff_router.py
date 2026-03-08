import sys
from pathlib import Path

import pytest
# TestClient fixture comes from backend/conftest.py, no need to import it here
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


def make_league_with_users(db, num_users=4):
    league = models.League(name='L1')
    db.add(league)
    db.commit()
    db.refresh(league)
    users = []
    for i in range(num_users):
        u = models.User(username=f'user{i}', email=None, hashed_password='h', league_id=league.id)
        db.add(u)
        users.append(u)
    db.commit()
    return league, users


def test_default_settings_and_update(client, api_db):
    db, _ = api_db
    league, _ = make_league_with_users(db)

    # GET default
    res = client.get(f'/playoffs/settings?league_id={league.id}')
    assert res.status_code == 200
    data = res.json()
    assert data['playoff_qualifiers'] == 6

    # PATCH qualifiers to 8
    patch = {'playoff_qualifiers': 8}
    res2 = client.patch(f'/playoffs/settings?league_id={league.id}', json=patch)
    assert res2.status_code == 200
    assert res2.json()['playoff_qualifiers'] == 8


def test_update_settings_rejects_invalid_payload(client, api_db):
    db, _ = api_db
    league, _ = make_league_with_users(db)

    invalid_patch = {
        'playoff_qualifiers': 7,
        'playoff_tiebreakers': ['wins', 'wins', 'coin_flip'],
    }
    res = client.patch(f'/playoffs/settings?league_id={league.id}', json=invalid_patch)
    assert res.status_code == 400


def test_generate_and_retrieve_bracket(client, api_db):
    db, _ = api_db
    league, users = make_league_with_users(db, num_users=6)

    # generate bracket for season 2026
    payload = {'league_id': league.id, 'season': 2026}
    res = client.post('/playoffs/generate', json=payload)
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'

    # retrieve bracket
    res2 = client.get(f'/playoffs/bracket?league_id={league.id}&season=2026')
    assert res2.status_code == 200
    bracket = res2.json()
    assert 'championship' in bracket
    # number of matches should equal qualifiers/2 rounded up (top seeds byes included)
    assert len(bracket['championship']) > 0
    # ensure at least one match has match_id
    assert isinstance(bracket['championship'][0]['match_id'], str)

    # override first match authoritatively
    first_id = bracket['championship'][0]['match_id']
    # suppose team_1_id is present
    team1 = bracket['championship'][0].get('team_1_id')
    res_override = client.put(f'/playoffs/match/{first_id}/override?league_id={league.id}&season=2026',
                              json={'winner_team_id': team1})
    assert res_override.status_code == 200
    assert res_override.json()['status'] == 'overridden'

    # reseed round 2 based on these results
    res_reseed = client.post('/playoffs/reseed', json={'league_id': league.id, 'season': 2026})
    assert res_reseed.status_code == 200
    assert res_reseed.json()['status'] == 'reseeded'

    # snapshot the bracket
    res_snap = client.post('/playoffs/snapshot', json={'league_id': league.id, 'season': 2026})
    assert res_snap.status_code == 200
    snapbody = res_snap.json()
    assert snapbody['status'] == 'snapped'
    assert isinstance(snapbody['id'], int)


def test_seasons_endpoint_returns_sorted_list(client, api_db):
    db, _ = api_db
    league, users = make_league_with_users(db, num_users=6)
    # create matches for two seasons
    db.add(models.PlayoffMatch(league_id=league.id, season=2024, match_id='a', round=1))
    db.add(models.PlayoffMatch(league_id=league.id, season=2025, match_id='b', round=1))
    db.commit()

    res = client.get(f'/playoffs/seasons?league_id={league.id}')
    assert res.status_code == 200
    data = res.json()
    assert data == [2025, 2024]

    # also verify it returns empty when no matches exist for a new league
    newleague = models.League(name='empty')
    db.add(newleague)
    db.commit()
    res2 = client.get(f'/playoffs/seasons?league_id={newleague.id}')
    assert res2.status_code == 200
    assert res2.json() == []


def test_generate_bracket_uses_dynamic_4_team_structure(client, api_db):
    db, _ = api_db
    league, _ = make_league_with_users(db, num_users=8)

    patch_res = client.patch(
        f'/playoffs/settings?league_id={league.id}',
        json={'playoff_qualifiers': 4, 'playoff_consolation': True},
    )
    assert patch_res.status_code == 200

    generate_res = client.post('/playoffs/generate', json={'league_id': league.id, 'season': 2026})
    assert generate_res.status_code == 200

    bracket_res = client.get(f'/playoffs/bracket?league_id={league.id}&season=2026')
    assert bracket_res.status_code == 200
    body = bracket_res.json()

    championship = body['championship']
    assert len(championship) == 2
    assert all(not m.get('is_bye') for m in championship)
    assert body['seeding_policy']['playoff_qualifiers'] == 4


def test_generate_bracket_uses_dynamic_6_team_structure_with_byes(client, api_db):
    db, _ = api_db
    league, _ = make_league_with_users(db, num_users=8)

    patch_res = client.patch(
        f'/playoffs/settings?league_id={league.id}',
        json={'playoff_qualifiers': 6, 'playoff_consolation': True},
    )
    assert patch_res.status_code == 200

    generate_res = client.post('/playoffs/generate', json={'league_id': league.id, 'season': 2026})
    assert generate_res.status_code == 200

    bracket_res = client.get(f'/playoffs/bracket?league_id={league.id}&season=2026')
    assert bracket_res.status_code == 200
    body = bracket_res.json()

    championship = body['championship']
    assert len(championship) == 4
    assert len([m for m in championship if m.get('is_bye')]) == 2
    assert body['seeding_policy']['playoff_qualifiers'] == 6


def test_generate_bracket_respects_consolation_toggle(client, api_db):
    db, _ = api_db
    league, _ = make_league_with_users(db, num_users=10)

    patch_res = client.patch(
        f'/playoffs/settings?league_id={league.id}',
        json={'playoff_qualifiers': 6, 'playoff_consolation': False},
    )
    assert patch_res.status_code == 200

    generate_res = client.post('/playoffs/generate', json={'league_id': league.id, 'season': 2026})
    assert generate_res.status_code == 200

    bracket_res = client.get(f'/playoffs/bracket?league_id={league.id}&season=2026')
    assert bracket_res.status_code == 200
    body = bracket_res.json()

    assert body['consolation'] == []
    assert body['seeding_policy']['playoff_consolation'] is False
