from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "DocuSync AI"
    DEBUG: bool = True
    ALLOWED_ORIGINS: list[str] = [
        "https://app.docusync.ai",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]

    # API Keys
    GROQ_API_KEY: str | None = ""
    GEMINI_API_KEY: str | None = ""
    GOOGLE_API_KEY: str | None = ""
    OPENROUTER_API_KEY: str = ""
    PRIMARY_EXTRACTION_MODEL: str = "llama-3.3-70b-versatile"
    VISION_EXTRACTION_MODEL: str = "gemini-2.5-flash"
    SECRET_KEY: str | None = None
    INITIAL_CA_USERNAME: str | None = None
    INITIAL_CA_PASSWORD: str | None = None
    INITIAL_CA_FULL_NAME: str = "Default CA Administrator"
    DEBUG_DEFAULT_CA_USERNAME: str = "ca_admin"
    DEBUG_DEFAULT_CA_PASSWORD: str = "Admin@123456"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEFAULT_PLATFORM_PORT: int = 10000

    # Database Settings (Defaults to SQLite for local development)
    DATABASE_URL: str = "sqlite:///storage/docusync.db"

    # Redis Broker Settings (Defaults to local Redis, overridable by Upstash)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage/export defaults
    UPLOAD_DIR: str = "storage/uploads"
    STORAGE_PUBLIC_PREFIX: str = "/storage/uploads"
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_STORAGE_BUCKET: str = "docusync-uploads"
    TALLY_FALLBACK_DATE: str = "20260101"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"dev", "development"}:
                return True
        return value

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Ensures compatibility with SQLAlchemy/SQLModel drivers across SQLite and PostgreSQL."""
        uri = self.DATABASE_URL
        if uri.startswith("postgres://"):
            return uri.replace("postgres://", "postgresql://", 1)
        return uri

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
