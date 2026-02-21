import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from core.security import get_current_active_superuser
from database import get_db
from main import app


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


@pytest.fixture
def client(api_db):
    db, _ = api_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_commissioner_list_returns_403_for_non_superuser(client):
    async def deny_superuser():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )

    app.dependency_overrides[get_current_active_superuser] = deny_superuser

    response = client.get('/admin/tools/commissioners')

    assert response.status_code == 403
    assert response.json()['detail'] == 'Superuser privileges required'


def test_create_and_list_commissioner_for_superuser(client, api_db, monkeypatch):
    db, _ = api_db

    league = models.League(name='Commissioner League')
    db.add(league)
    db.commit()
    db.refresh(league)

    async def allow_superuser():
        return models.User(id=999, username='root', is_superuser=True)

    app.dependency_overrides[get_current_active_superuser] = allow_superuser

    monkeypatch.setattr('routers.platform_tools.get_password_hash', lambda _value: 'hashed-test-password')
    monkeypatch.setattr('routers.platform_tools.send_invite_email', lambda *args, **kwargs: True)

    create_res = client.post(
        '/admin/tools/commissioners',
        json={
            'username': 'comm-new',
            'email': 'comm-new@test.com',
            'league_id': league.id,
        },
    )

    assert create_res.status_code == 200
    payload = create_res.json()
    assert payload['message'] == 'Commissioner invited.'
    assert payload['commissioner']['username'] == 'comm-new'
    assert payload['commissioner']['league_id'] == league.id
    assert payload['debug_password']

    list_res = client.get('/admin/tools/commissioners')
    assert list_res.status_code == 200
    commissioners = list_res.json()
    assert len(commissioners) == 1
    assert commissioners[0]['username'] == 'comm-new'


def test_update_commissioner_updates_fields(client, api_db):
    db, _ = api_db

    league_one = models.League(name='League One')
    league_two = models.League(name='League Two')
    commissioner = models.User(
        username='comm-old',
        email='comm-old@test.com',
        hashed_password='hashed',
        is_commissioner=True,
        league_id=1,
    )
    db.add_all([league_one, league_two, commissioner])
    db.commit()
    db.refresh(commissioner)

    async def allow_superuser():
        return models.User(id=1000, username='root', is_superuser=True)

    app.dependency_overrides[get_current_active_superuser] = allow_superuser

    res = client.put(
        f'/admin/tools/commissioners/{commissioner.id}',
        json={
            'username': 'comm-updated',
            'email': 'comm-updated@test.com',
            'league_id': league_two.id,
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body['message'] == 'Commissioner updated.'
    assert body['commissioner']['username'] == 'comm-updated'
    assert body['commissioner']['email'] == 'comm-updated@test.com'
    assert body['commissioner']['league_id'] == league_two.id


def test_remove_commissioner_blocks_superuser_and_allows_normal_commissioner(client, api_db):
    db, _ = api_db

    super_commish = models.User(
        username='super-comm',
        email='super-comm@test.com',
        hashed_password='hashed',
        is_commissioner=True,
        is_superuser=True,
    )
    normal_commish = models.User(
        username='normal-comm',
        email='normal-comm@test.com',
        hashed_password='hashed',
        is_commissioner=True,
        is_superuser=False,
    )
    db.add_all([super_commish, normal_commish])
    db.commit()
    db.refresh(super_commish)
    db.refresh(normal_commish)

    async def allow_superuser():
        return models.User(id=1001, username='root', is_superuser=True)

    app.dependency_overrides[get_current_active_superuser] = allow_superuser

    blocked = client.delete(f'/admin/tools/commissioners/{super_commish.id}')
    assert blocked.status_code == 400
    assert 'Cannot remove commissioner access from a superuser' in blocked.json()['detail']

    allowed = client.delete(f'/admin/tools/commissioners/{normal_commish.id}')
    assert allowed.status_code == 200
    assert allowed.json()['message'] == 'Commissioner access removed.'

    db.refresh(normal_commish)
    assert normal_commish.is_commissioner is False
