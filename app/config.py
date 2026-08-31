from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "DocuSync AI"
    DEBUG: bool = True
    GROQ_API_KEY: Optional[str] = ""
    OPENROUTER_API_KEY: str = ""
    PRIMARY_EXTRACTION_MODEL: str = "llama-3.3-70b-versatile"
    DATABASE_URL: str = "sqlite:///storage/docusync.db"
    SECRET_KEY: str = "default_secret_key_change_me_in_production"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",extra="ignore")

settings = Settings()