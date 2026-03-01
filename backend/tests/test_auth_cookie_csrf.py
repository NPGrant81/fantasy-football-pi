import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core import security
from backend.database import get_db
from backend.main import app


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

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "cookie-user"


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
