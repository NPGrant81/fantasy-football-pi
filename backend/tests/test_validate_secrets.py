import pytest

from backend.scripts import validate_secrets


def test_check_environment_variables_skips_non_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    # Non-production should not enforce required secret checks.
    validate_secrets.check_environment_variables()


def test_check_environment_variables_requires_secret_key_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(validate_secrets.ValidationError, match="SECRET_KEY is not set"):
        validate_secrets.check_environment_variables()


def test_check_environment_variables_rejects_weak_pattern(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "default-secret-value-that-is-long-enough-123")

    with pytest.raises(validate_secrets.ValidationError, match="contains weak pattern"):
        validate_secrets.check_environment_variables()


def test_check_environment_variables_accepts_strong_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8")

    validate_secrets.check_environment_variables()
