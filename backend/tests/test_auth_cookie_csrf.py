import sys
from pathlib import Path
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from jose import jwt

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core import security
from backend.database import get_db
from backend.main import app
from backend.routers import auth as auth_router


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
def override_dependencies(api_db):
    def override_get_db():
        try:
            yield api_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def test_login_sets_auth_and_csrf_cookies(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret"
        and hashed_password == "test-hash",
    )

    user = models.User(
        username="cookie-user",
        email="cookie-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    response = client.post(
        "/auth/token",
        data={"username": "cookie-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    assert "ffpi_access_token" in response.cookies
    assert "ffpi_csrf_token" in response.cookies
    assert "ffpi_refresh_token" in response.cookies

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "cookie-user"


def test_login_username_match_is_case_insensitive(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret"
        and hashed_password == "test-hash",
    )

    user = models.User(
        username="CaseSensitiveUser",
        email="case-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    response = client.post(
        "/auth/token",
        data={"username": "casesensitiveuser", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    assert response.json()["owner_id"] == user.id


def test_csrf_required_for_cookie_authenticated_write_requests(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret"
        and hashed_password == "test-hash",
    )

    user = models.User(
        username="csrf-user",
        email="csrf-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    login = client.post(
        "/auth/token",
        data={"username": "csrf-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200

    blocked = client.put("/auth/email", json={"email": "new-email@test.com"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "CSRF token validation failed"

    csrf_token = login.cookies.get("ffpi_csrf_token")
    allowed = client.put(
        "/auth/email",
        json={"email": "new-email@test.com"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert allowed.status_code == 200
    assert allowed.json()["email"] == "new-email@test.com"


def test_login_with_malformed_hash_returns_401_not_500(client, api_db):
    user = models.User(
        username="legacy-hash-user",
        email="legacy-hash-user@test.com",
        hashed_password="h",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    response = client.post(
        "/auth/token",
        data={"username": "legacy-hash-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_unauthenticated_auth_me_preserves_www_authenticate_header(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_logout_revokes_token_and_blocks_reuse(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret"
        and hashed_password == "test-hash",
    )

    user = models.User(
        username="revocation-user",
        email="revocation-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    login = client.post(
        "/auth/token",
        data={"username": "revocation-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200

    access_token = login.json()["access_token"]
    csrf_token = login.cookies.get("ffpi_csrf_token")
    refresh_token = login.cookies.get("ffpi_refresh_token")
    assert csrf_token
    assert refresh_token

    logout = client.post("/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout.status_code == 200

    refresh_hash = security.hash_refresh_token(refresh_token)
    refresh_row = (
        api_db.query(models.RefreshToken)
        .filter(models.RefreshToken.token_hash == refresh_hash)
        .first()
    )
    assert refresh_row is not None
    assert refresh_row.revoked_at is not None

    # Re-inject the previously issued token; revocation should block it.
    client.cookies.set("ffpi_access_token", access_token)
    blocked = client.get("/auth/me")
    assert blocked.status_code == 401


def test_revocation_survives_fresh_client_session(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret"
        and hashed_password == "test-hash",
    )

    user = models.User(
        username="revocation-persist-user",
        email="revocation-persist-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    login = client.post(
        "/auth/token",
        data={"username": "revocation-persist-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200

    access_token = login.json()["access_token"]
    payload = jwt.decode(
        access_token,
        security.SECRET_KEY,
        algorithms=[security.ALGORITHM],
        options={"verify_exp": False},
    )
    jti = payload.get("jti")
    assert jti

    csrf_token = login.cookies.get("ffpi_csrf_token")
    assert csrf_token
    logout = client.post("/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout.status_code == 200

    assert api_db.query(models.RevokedToken).filter(models.RevokedToken.jti == jti).first() is not None

    # Simulate a fresh process/client using the same persisted database rows.
    original = app.router.lifespan_context

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    app.router.lifespan_context = noop_lifespan
    try:
        with TestClient(app) as fresh_client:
            fresh_client.cookies.set("ffpi_access_token", access_token)
            blocked = fresh_client.get("/auth/me")
            assert blocked.status_code == 401
    finally:
        app.router.lifespan_context = original


def test_refresh_rotates_refresh_token_and_issues_new_access_token(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret"
        and hashed_password == "test-hash",
    )

    user = models.User(
        username="refresh-rotate-user",
        email="refresh-rotate-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    login = client.post(
        "/auth/token",
        data={"username": "refresh-rotate-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200

    old_refresh_token = login.cookies.get("ffpi_refresh_token")
    csrf_token = login.cookies.get("ffpi_csrf_token")
    assert old_refresh_token
    assert csrf_token

    refresh = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf_token})
    assert refresh.status_code == 200
    assert refresh.json().get("access_token")

    new_refresh_token = refresh.cookies.get("ffpi_refresh_token")
    assert new_refresh_token
    assert new_refresh_token != old_refresh_token

    old_hash = security.hash_refresh_token(old_refresh_token)
    old_record = (
        api_db.query(models.RefreshToken)
        .filter(models.RefreshToken.token_hash == old_hash)
        .first()
    )
    assert old_record is not None
    assert old_record.revoked_at is not None

    new_hash = security.hash_refresh_token(new_refresh_token)
    new_record = (
        api_db.query(models.RefreshToken)
        .filter(models.RefreshToken.token_hash == new_hash)
        .first()
    )
    assert new_record is not None
    assert new_record.revoked_at is None
    assert new_record.rotated_from_token_hash == old_hash


def test_refresh_requires_csrf_when_access_cookie_missing(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret"
        and hashed_password == "test-hash",
    )

    user = models.User(
        username="refresh-csrf-user",
        email="refresh-csrf-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    login = client.post(
        "/auth/token",
        data={"username": "refresh-csrf-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200

    # Simulate expired access cookie while refresh cookie still exists.
    client.cookies.delete("ffpi_access_token")

    refresh = client.post("/auth/refresh")
    assert refresh.status_code == 403
    assert refresh.json()["detail"] == "CSRF token validation failed"


def test_refresh_skips_csrf_when_cookie_auth_disabled(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret"
        and hashed_password == "test-hash",
    )
    monkeypatch.setattr(auth_router, "USE_COOKIE_AUTH", False)

    user = models.User(
        username="refresh-no-cookie-auth-user",
        email="refresh-no-cookie-auth-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    login = client.post(
        "/auth/token",
        data={"username": "refresh-no-cookie-auth-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200

    refresh = client.post("/auth/refresh")
    assert refresh.status_code == 401
    assert refresh.json()["detail"] == "Refresh token missing"


def test_choose_auth_token_respects_allow_bearer_auth(monkeypatch):
    monkeypatch.setattr(security, "ALLOW_BEARER_AUTH", False)
    assert security.choose_auth_token(None, "bearer-token") is None

    monkeypatch.setattr(security, "ALLOW_BEARER_AUTH", True)
    assert security.choose_auth_token(None, "bearer-token") == "bearer-token"
def test_refresh_replay_revokes_all_refresh_tokens(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret"
        and hashed_password == "test-hash",
    )

    user = models.User(
        username="refresh-replay-user",
        email="refresh-replay-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    login = client.post(
        "/auth/token",
        data={"username": "refresh-replay-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200

    old_refresh_token = login.cookies.get("ffpi_refresh_token")
    csrf_token = login.cookies.get("ffpi_csrf_token")
    assert old_refresh_token
    assert csrf_token

    first_refresh = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf_token})
    assert first_refresh.status_code == 200

    client.cookies.set("ffpi_refresh_token", old_refresh_token)
    replay_csrf = client.cookies.get("ffpi_csrf_token")
    replay_attempt = client.post("/auth/refresh", headers={"X-CSRF-Token": replay_csrf})
    assert replay_attempt.status_code == 401
    assert replay_attempt.json()["detail"] == "Refresh token replay detected"

    active_tokens = (
        api_db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.user_id == user.id,
            models.RefreshToken.revoked_at.is_(None),
        )
        .count()
    )
    assert active_tokens == 0
