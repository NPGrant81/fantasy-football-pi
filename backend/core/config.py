from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
DEVELOPMENT_SECRET = "dev_secret_only_not_for_production"
WEAK_SECRET_PATTERNS = (
    "change-me-in-production",
    "your-secret-key-here",
    "secret",
    "test",
    "debug",
    "default",
    "insecure",
)


def current_app_env(default: str = "development") -> str:
    return os.getenv("APP_ENV", os.getenv("ENVIRONMENT", default)).strip().lower()


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )
    secret_key: str = Field(default=DEVELOPMENT_SECRET, validation_alias="SECRET_KEY")
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    auto_seed_on_startup: bool = Field(default=False, validation_alias="AUTO_SEED_ON_STARTUP")
    allowed_hosts_csv: str = Field(
        default="localhost,127.0.0.1,testserver",
        validation_alias="ALLOWED_HOSTS",
    )
    frontend_allowed_origins_csv: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="FRONTEND_ALLOWED_ORIGINS",
    )
    allow_all_origins: bool = Field(default=False, validation_alias="ALLOW_ALL_ORIGINS")
    access_token_cookie_name: str = Field(
        default="ffpi_access_token",
        validation_alias="ACCESS_TOKEN_COOKIE_NAME",
    )
    csrf_cookie_name: str = Field(default="ffpi_csrf_token", validation_alias="CSRF_COOKIE_NAME")
    csrf_header_name: str = Field(default="X-CSRF-Token", validation_alias="CSRF_HEADER_NAME")
    use_cookie_auth: bool = Field(default=True, validation_alias="USE_COOKIE_AUTH")
    auth_cookie_secure: bool = Field(default=False, validation_alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        validation_alias="AUTH_COOKIE_SAMESITE",
    )
    refresh_token_cookie_name: str = Field(
        default="ffpi_refresh_token",
        validation_alias="REFRESH_TOKEN_COOKIE_NAME",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env in {"production", "prod"}

    @staticmethod
    def _parse_csv(raw_value: str) -> list[str]:
        return [value.strip() for value in raw_value.split(",") if value.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return self._parse_csv(self.allowed_hosts_csv)

    @property
    def frontend_allowed_origins(self) -> list[str]:
        return self._parse_csv(self.frontend_allowed_origins_csv)

    @property
    def cors_origins(self) -> list[str]:
        return ["*"] if self.allow_all_origins else self.frontend_allowed_origins

    @model_validator(mode="after")
    def validate_runtime_contract(self) -> "RuntimeSettings":
        self.app_env = self.app_env.strip().lower()

        supported_environments = {"development", "test", "testing", "production", "prod"}
        if self.app_env not in supported_environments:
            raise ValueError(f"APP_ENV must be one of {sorted(supported_environments)}")

        if not self.is_production:
            return self

        if not self.database_url:
            raise ValueError("DATABASE_URL is required in production environment")

        if not self.secret_key or self.secret_key == DEVELOPMENT_SECRET:
            raise ValueError("SECRET_KEY is not set in production environment")

        secret_lower = self.secret_key.lower()
        for pattern in WEAK_SECRET_PATTERNS:
            if pattern in secret_lower:
                raise ValueError(f"SECRET_KEY contains weak pattern '{pattern}' in production")

        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")

        if self.auto_seed_on_startup:
            raise ValueError("AUTO_SEED_ON_STARTUP must be disabled in production")

        if self.allow_all_origins or "*" in self.frontend_allowed_origins:
            raise ValueError("Wildcard CORS origins are not allowed in production")

        local_hosts = {"localhost", "127.0.0.1", "testserver"}
        if (
            not self.allowed_hosts
            or "*" in self.allowed_hosts
            or not any(host not in local_hosts for host in self.allowed_hosts)
        ):
            raise ValueError("ALLOWED_HOSTS must contain explicit production hosts")

        if not self.frontend_allowed_origins or any(
            not origin.startswith("https://")
            for origin in self.frontend_allowed_origins
        ):
            raise ValueError("FRONTEND_ALLOWED_ORIGINS must contain only HTTPS production origins")

        if not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE must be enabled in production")

        return self


@lru_cache
def get_settings() -> RuntimeSettings:
    return RuntimeSettings()
