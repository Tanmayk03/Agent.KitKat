"""
Agent KitKat - Database Connection & Session Management
Using Async SQLAlchemy with SQLite (aiosqlite).
"""

from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from backend.config import get_settings

settings = get_settings()

# Create async SQLite engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Declarative base model
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions to FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize all database tables defined in models and ensure storage directories exist."""
    import os
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    os.makedirs(settings.RESUMES_DIR, exist_ok=True)
    os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(settings.APPLICATIONS_DIR, exist_ok=True)
    os.makedirs(settings.LOGS_DIR, exist_ok=True)

    # Ensure models are imported so Base knows about them
    import backend.database.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Automatic schema migrations for new Phase 6 columns
        migrations = [
            "ALTER TABLE application_drafts ADD COLUMN pre_submit_screenshot VARCHAR(500)",
            "ALTER TABLE application_drafts ADD COLUMN post_submit_screenshot VARCHAR(500)",
            "ALTER TABLE applications ADD COLUMN pre_submit_screenshot VARCHAR(500)",
            "ALTER TABLE applications ADD COLUMN post_submit_screenshot VARCHAR(500)",
            "ALTER TABLE applications ADD COLUMN browser_logs JSON",
            # Stage 2
            "ALTER TABLE jobs ADD COLUMN employment_type VARCHAR(100)",
            "ALTER TABLE jobs ADD COLUMN posted_at VARCHAR(40)",
            "ALTER TABLE jobs ADD COLUMN fetched_at DATETIME",
            "ALTER TABLE eligibility_results ADD COLUMN experience_status VARCHAR(20)",
            "ALTER TABLE eligibility_results ADD COLUMN experience_details VARCHAR(500)",
        ]
        for stmt in migrations:
            try:
                await conn.execute(text(stmt))
            except OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
