"""
Agent KitKat - Application Configuration
Centralized configuration management using pydantic-settings.

All relative storage / database paths are resolved against the project root,
so the backend uses the same database no matter which folder it is started from.
Every setting can be overridden with an environment variable of the same name
(tests use this to point at a throwaway database).
"""

import os
from functools import lru_cache
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Also expose .env values as environment variables (optional keys such as ADZUNA_APP_ID and
# SIMPLIFY_INTERNSHIPS_URL are read with os.getenv). Real environment variables win.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)
except ImportError:  # python-dotenv is in requirements.txt; tolerate its absence
    pass


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(PROJECT_ROOT, path))


class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "Agent KitKat"
    APP_FULL_NAME: str = "Agent KitKat - Autonomous AI Career Assistant"
    APP_TAGLINE: str = "Your little buddy for finding your next opportunity."
    APP_VERSION: str = "1.0.0-rc.1"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Your local timezone: daily reports and "today" are computed in it (IANA name)
    TIMEZONE: str = "Asia/Kolkata"

    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Extra browser origins allowed to call the API (comma separated).
    # localhost / 127.0.0.1 and private-LAN origins (10.x, 172.16-31.x, 192.168.x)
    # are always allowed; everything else is rejected.
    CORS_EXTRA_ORIGINS: str = ""

    # Local Ollama AI Settings
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:1.5b"
    OLLAMA_REQUEST_TIMEOUT_SECONDS: float = 120.0

    # Outbound HTTP: honour system HTTP(S)_PROXY settings (needed on some college/corporate networks)
    HTTP_TRUST_ENV: bool = False

    # Database & Storage Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///storage/agent_kitkat.db"
    STORAGE_DIR: str = "storage"
    RESUMES_DIR: str = "storage/resumes"
    APPLICATIONS_DIR: str = "storage/applications"
    SCREENSHOTS_DIR: str = "storage/screenshots"
    LOGS_DIR: str = "storage/logs"

    # Optional, git-ignored file used to seed a brand new profile (never commit personal data)
    PROFILE_SEED_FILE: str = "profile_seed.json"

    # Uploads
    MAX_UPLOAD_MB: int = 10

    # Browser Automation Settings
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT_MS: int = 30000
    BROWSER_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

    model_config = SettingsConfigDict(
        env_file=os.path.join(PROJECT_ROOT, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        for name in ("STORAGE_DIR", "RESUMES_DIR", "APPLICATIONS_DIR", "SCREENSHOTS_DIR", "LOGS_DIR", "PROFILE_SEED_FILE"):
            setattr(self, name, _abs(getattr(self, name)))
        prefix = "sqlite+aiosqlite:///"
        if self.DATABASE_URL.startswith(prefix):
            db_path = self.DATABASE_URL[len(prefix):]
            if db_path and db_path != ":memory:":
                self.DATABASE_URL = prefix + _abs(db_path).replace("\\", "/")
        return self

    @property
    def cors_extra_origins(self) -> List[str]:
        return [o.strip().rstrip("/") for o in self.CORS_EXTRA_ORIGINS.split(",") if o.strip()]

    @property
    def database_path(self) -> str:
        prefix = "sqlite+aiosqlite:///"
        return self.DATABASE_URL[len(prefix):] if self.DATABASE_URL.startswith(prefix) else ""


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
