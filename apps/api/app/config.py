"""Application configuration."""

from typing import Any, List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "change-me-in-production"
PRODUCTION_ENVIRONMENTS = {"production", "prod", "staging"}
# RFC 7518 section 3.2: an HMAC key for HS256 must be at least as long as the
# hash output.
MINIMUM_SECRET_KEY_BYTES = 32


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Database
    database_url: str = "postgresql://epiro:epiro_password@localhost:5432/epiro"
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    secret_key: str = DEFAULT_SECRET_KEY

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    refresh_token_expiry_days: int = 7

    # Environment
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_format: str = "text"

    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # Rate limiting
    rate_limit_enabled: bool = True
    # In-process by default; point at Redis when running multiple workers.
    rate_limit_storage_uri: str = "memory://"
    rate_limit_login_per_minute: int = 5
    rate_limit_public_write_per_minute: int = 10
    # The public portal is meant to be read, so this is generous; it exists to
    # stop one client from monopolising the database, not to ration access.
    rate_limit_public_read_per_minute: int = 120

    # Organization
    org_name: str = "EPIRO"
    org_country: str = "NG"
    org_timezone: str = "Africa/Lagos"

    # AI/LLM
    openai_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4-turbo"

    # Storage
    storage_type: str = "local"
    storage_path: str = "/data"
    aws_s3_bucket: Optional[str] = None
    aws_region: Optional[str] = None

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    sender_email: str = "noreply@epiro.local"

    # Features
    feature_ai_assistant: bool = True
    feature_rag: bool = True
    feature_offline_mode: bool = True
    feature_multilingual: bool = True

    # Security
    mfa_enabled: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        """Accept the comma-separated form documented in .env.example.

        Pydantic would otherwise require JSON for a list field, so the
        documented CORS_ORIGINS value failed to parse at startup.
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _validate_secret_key_outside_development(self) -> "Settings":
        """Refuse to start a deployed environment with a weak signing key.

        The shipped default is public, so any token signed with it is
        forgeable; a short key weakens HS256 regardless of secrecy.
        """
        if self.environment.lower() not in PRODUCTION_ENVIRONMENTS:
            return self

        deployed = ", ".join(sorted(PRODUCTION_ENVIRONMENTS))

        if self.secret_key == DEFAULT_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be set to a unique value when ENVIRONMENT is "
                f"one of: {deployed}"
            )

        if len(self.secret_key.encode("utf-8")) < MINIMUM_SECRET_KEY_BYTES:
            raise ValueError(
                f"SECRET_KEY must be at least {MINIMUM_SECRET_KEY_BYTES} bytes "
                f"when ENVIRONMENT is one of: {deployed}"
            )

        return self


settings = Settings()
