"""
Agent KitKat - Application Configuration
Centralized configuration management using pydantic-settings.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "Agent KitKat"
    APP_FULL_NAME: str = "Agent KitKat - Autonomous AI Career Assistant"
    APP_TAGLINE: str = "Your little buddy for finding your next opportunity."
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Local Ollama AI Settings
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:1.5b"
    OLLAMA_REQUEST_TIMEOUT_SECONDS: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
