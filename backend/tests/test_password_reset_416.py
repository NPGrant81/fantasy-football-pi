"""Tests for password reset functionality (Issue #416)."""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from backend.core import security
from backend.database import get_db
from backend.main import app
from backend.services import password_reset_service


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


@pytest.fixture
def test_user(api_db):
    user = models.User(
        username="reset-user",
        email="reset-user@test.com",
        hashed_password=security.get_password_hash("OldPassword123!"),
        league_id=1,
    )
    api_db.add(user)
    api_db.commit()
    api_db.refresh(user)
    return user


def test_hash_reset_token_consistency():
    token = "my-secret-token-12345"
    hash1 = password_reset_service.hash_reset_token(token)
    hash2 = password_reset_service.hash_reset_token(token)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_create_reset_request_revokes_previous_token(api_db, test_user):
    token1 = password_reset_service.create_password_reset_request(api_db, test_user)
    token2 = password_reset_service.create_password_reset_request(api_db, test_user)

    token1_hash = password_reset_service.hash_reset_token(token1)
    token2_hash = password_reset_service.hash_reset_token(token2)

    old_token = api_db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token_hash == token1_hash
    ).first()
    new_token = api_db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token_hash == token2_hash
    ).first()

    assert old_token is None
    assert new_token is not None


def test_validate_and_use_token_single_use(api_db, test_user):
    token = password_reset_service.create_password_reset_request(api_db, test_user)
    assert password_reset_service.validate_and_use_reset_token(api_db, test_user.id, token) is True
    with pytest.raises(ValueError, match="Token already used"):
        password_reset_service.validate_and_use_reset_token(api_db, test_user.id, token)


def test_validate_and_use_token_expired(api_db, test_user):
    token = password_reset_service.generate_reset_token()
    token_hash = password_reset_service.hash_reset_token(token)
    api_db.add(
        models.PasswordResetToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    api_db.commit()

    with pytest.raises(ValueError, match="Token expired"):
        password_reset_service.validate_and_use_reset_token(api_db, test_user.id, token)


def test_password_reset_request_anti_enumeration(client, api_db, test_user):
    known = client.post("/auth/password-reset-request", json={"email": test_user.email})
    unknown = client.post("/auth/password-reset-request", json={"email": "missing@example.com"})

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]

    tokens = api_db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == test_user.id
    ).all()
    assert len(tokens) == 1


def test_password_reset_confirm_success(client, api_db, test_user):
    token = password_reset_service.create_password_reset_request(api_db, test_user)
    new_password = "NewPassword123!"

    response = client.post(
        "/auth/password-reset-confirm",
        json={"token": token, "new_password": new_password},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Password reset successfully"

    api_db.refresh(test_user)
    assert security.verify_password(new_password, test_user.hashed_password)


def test_password_reset_confirm_invalid_token(client):
    response = client.post(
        "/auth/password-reset-confirm",
        json={"token": "invalid-token", "new_password": "NewPassword123!"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset token"


def test_password_reset_confirm_weak_password(client, api_db, test_user):
    token = password_reset_service.create_password_reset_request(api_db, test_user)
    response = client.post(
        "/auth/password-reset-confirm",
        json={"token": token, "new_password": "short"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Password must be at least 8 characters long"
