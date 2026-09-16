"""Application configuration."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = "postgresql://epiro:epiro_password@localhost:5432/epiro"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    secret_key: str = "change-me-in-production"

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

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

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

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


settings = Settings()
