"""Application settings loaded from environment variables.

Uses Pydantic Settings for type-safe, validated configuration. Settings are
loaded once at startup and accessed via the `get_settings()` cached function.

For production, prefer loading via a secrets manager (AWS Secrets Manager,
Doppler, etc.) over .env files.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Type-safe application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ─── App ────────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "fastapi-starter"
    app_debug: bool = False
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    app_log_json: bool = False

    # ─── Server ─────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"  # noqa: S104 — explicit bind, container-friendly
    port: int = 8000

    # ─── Security ───────────────────────────────────────────────────────────
    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production-min-32-chars-required-12345"),
        description="Used to sign JWT tokens. Generate with: secrets.token_urlsafe(64)",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    api_key_header: str = "X-API-Key"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v: str | list[str]) -> list[str]:
        # Allow comma-separated string from env var.
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("secret_key")
    @classmethod
    def _secret_must_be_strong(cls, v: SecretStr, info) -> SecretStr:
        # Enforce strong secret in non-dev environments.
        data = info.data
        env = data.get("app_env", "development")
        if env != "development" and len(v.get_secret_value()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in non-dev environments")
        return v

    # ─── Database ───────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_echo: bool = False

    # ─── Redis ──────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ─── Rate limiting ──────────────────────────────────────────────────────
    rate_limit_default: str = "100/minute"
    rate_limit_login: str = "5/minute"

    # ─── Observability ──────────────────────────────────────────────────────
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — call this anywhere, instantiated once."""
    return Settings()
