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


def test_health_contract_shape(client):
    response = client.get("/health")
    assert response.status_code in {200, 503}

    payload = response.json()
    assert set(payload.keys()) == {"status", "service", "database"}
    assert payload["status"] in {"ok", "degraded"}
    assert payload["service"] == "fantasy-football-backend"
    assert payload["database"] in {"ok", "error"}


def test_auth_token_contract_shape(client, api_db, monkeypatch):
    monkeypatch.setattr(
        security,
        "verify_password",
        lambda plain_password, hashed_password: plain_password == "secret" and hashed_password == "test-hash",
    )

    user = models.User(
        username="contract-user",
        email="contract-user@test.com",
        hashed_password="test-hash",
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()

    response = client.post(
        "/auth/token",
        data={"username": "contract-user", "password": "secret"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert "access_token" in payload
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"
    assert isinstance(payload.get("owner_id"), int)


def test_openapi_contract_contains_required_paths(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200

    payload = response.json()
    paths = payload.get("paths", {})
    assert "/auth/token" in paths
    assert "/health" in paths
