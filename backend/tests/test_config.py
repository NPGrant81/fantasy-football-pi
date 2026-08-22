import pytest
from pydantic import ValidationError

from backend.core.config import DEVELOPMENT_SECRET, RuntimeSettings, current_app_env


PRODUCTION_VALUES = {
    "app_env": "production",
    "secret_key": "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
    "allowed_hosts_csv": "api.example.com,localhost",
    "frontend_allowed_origins_csv": "https://app.example.com",
}


def test_settings_use_development_defaults(monkeypatch):
    for name in ("APP_ENV", "ENVIRONMENT", "SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)

    settings = RuntimeSettings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.secret_key == DEVELOPMENT_SECRET
    assert not settings.is_production


def test_settings_support_legacy_environment_name(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("SECRET_KEY", PRODUCTION_VALUES["secret_key"])
    monkeypatch.setenv("ALLOWED_HOSTS", PRODUCTION_VALUES["allowed_hosts_csv"])
    monkeypatch.setenv(
        "FRONTEND_ALLOWED_ORIGINS",
        PRODUCTION_VALUES["frontend_allowed_origins_csv"],
    )

    settings = RuntimeSettings(_env_file=None)

    assert settings.is_production


def test_current_app_env_prefers_runtime_app_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_ENV", "PRODUCTION")

    assert current_app_env() == "production"


def test_settings_parse_runtime_host_and_origin_lists():
    settings = RuntimeSettings(
        allowed_hosts_csv="localhost, api.example.com",
        frontend_allowed_origins_csv="http://localhost:5173, https://app.example.com",
        _env_file=None,
    )

    assert settings.allowed_hosts == ["localhost", "api.example.com"]
    assert settings.frontend_allowed_origins == [
        "http://localhost:5173",
        "https://app.example.com",
    ]


def test_settings_require_secret_in_production():
    with pytest.raises(ValidationError, match="SECRET_KEY is not set"):
        RuntimeSettings(
            **{**PRODUCTION_VALUES, "secret_key": DEVELOPMENT_SECRET},
            _env_file=None,
        )


def test_settings_reject_weak_production_secret():
    with pytest.raises(ValidationError, match="contains weak pattern"):
        RuntimeSettings(
            **{
                **PRODUCTION_VALUES,
                "secret_key": "default-secret-value-that-is-long-enough-123",
            },
            _env_file=None,
        )


def test_settings_reject_wildcard_production_cors():
    with pytest.raises(ValidationError, match="Wildcard CORS origins"):
        RuntimeSettings(
            **PRODUCTION_VALUES,
            allow_all_origins=True,
            _env_file=None,
        )


def test_settings_reject_production_auto_seed():
    with pytest.raises(ValidationError, match="AUTO_SEED_ON_STARTUP"):
        RuntimeSettings(
            **PRODUCTION_VALUES,
            auto_seed_on_startup=True,
            _env_file=None,
        )


def test_settings_accept_explicit_production_configuration():
    settings = RuntimeSettings(**PRODUCTION_VALUES, _env_file=None)

    assert settings.is_production
    assert settings.allowed_hosts == ["api.example.com", "localhost"]
    assert settings.cors_origins == ["https://app.example.com"]
