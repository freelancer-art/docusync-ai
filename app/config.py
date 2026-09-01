import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "DocuSync AI"
    DEBUG: bool = True

    # API Keys
    GROQ_API_KEY: str | None = ""
    OPENROUTER_API_KEY: str = ""
    PRIMARY_EXTRACTION_MODEL: str = "llama-3.3-70b-versatile"
    SECRET_KEY: str = "default_secret_key_change_me_in_production"

    # Database Settings (Defaults to SQLite for local development)
    DATABASE_URL: str = "sqlite:///storage/docusync.db"

    # Redis Broker Settings (Defaults to local Redis, overridable by Upstash)
    REDIS_URL: str = "redis://localhost:6379/0"

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