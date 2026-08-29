import pytest
from pydantic import ValidationError

from backend.core.config import DEVELOPMENT_SECRET, RuntimeSettings, current_app_env


PRODUCTION_VALUES = {
    "app_env": "production",
    "secret_key": "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
    "database_url": "postgresql://ffpi:password@db.example.com/fantasy_football",
    "allowed_hosts_csv": "api.example.com,localhost",
    "frontend_allowed_origins_csv": "https://app.example.com",
    "auth_cookie_secure": True,
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
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "1")
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


def test_settings_reject_unknown_environment():
    with pytest.raises(ValidationError, match="APP_ENV must be one of"):
        RuntimeSettings(app_env="prd", _env_file=None)


def test_settings_require_database_url_in_production():
    with pytest.raises(ValidationError, match="DATABASE_URL is required"):
        RuntimeSettings(
            **{**PRODUCTION_VALUES, "database_url": None},
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


def test_settings_validation_error_hides_secret_input():
    secret_value = "default-sensitive-marker-that-must-not-leak-123"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeSettings(
            **{**PRODUCTION_VALUES, "secret_key": secret_value},
            _env_file=None,
        )

    assert secret_value not in str(exc_info.value)


def test_settings_reject_wildcard_production_cors():
    with pytest.raises(ValidationError, match="Wildcard CORS origins"):
        RuntimeSettings(
            **PRODUCTION_VALUES,
            allow_all_origins=True,
            _env_file=None,
        )


def test_settings_reject_http_production_origin():
    with pytest.raises(ValidationError, match="only HTTPS production origins"):
        RuntimeSettings(
            **{
                **PRODUCTION_VALUES,
                "frontend_allowed_origins_csv": "http://app.example.com",
            },
            _env_file=None,
        )


def test_settings_require_secure_production_cookies():
    with pytest.raises(ValidationError, match="AUTH_COOKIE_SECURE"):
        RuntimeSettings(
            **{**PRODUCTION_VALUES, "auth_cookie_secure": False},
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
