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
            # Stage 3
            "ALTER TABLE jobs ADD COLUMN last_seen_at DATETIME",
            "ALTER TABLE jobs ADD COLUMN expired_at DATETIME",
            "ALTER TABLE jobs ADD COLUMN expiry_evidence VARCHAR(255)",
            "ALTER TABLE jobs ADD COLUMN dedupe_key VARCHAR(600)",
            "ALTER TABLE jobs ADD COLUMN url_key VARCHAR(1000)",
            "CREATE INDEX IF NOT EXISTS ix_jobs_dedupe_key ON jobs (dedupe_key)",
            "CREATE INDEX IF NOT EXISTS ix_jobs_url_key ON jobs (url_key)",
            "CREATE INDEX IF NOT EXISTS ix_jobs_source_ext ON jobs (source, job_id_external)",
            # Stage 4
            "ALTER TABLE eligibility_results ADD COLUMN checks_json JSON",
            "ALTER TABLE match_results ADD COLUMN details_json JSON",
            "ALTER TABLE user_profiles ADD COLUMN work_authorized_countries JSON",
            # Stage 5
            "ALTER TABLE application_drafts ADD COLUMN grounding_report JSON",
            "ALTER TABLE application_drafts ADD COLUMN current_version INTEGER",
            "ALTER TABLE applications ADD COLUMN stage VARCHAR(30)",
            "ALTER TABLE applications ADD COLUMN stage_updated_at DATETIME",
            "ALTER TABLE applications ADD COLUMN resume_id VARCHAR(36)",
            "ALTER TABLE applications ADD COLUMN resume_file_name VARCHAR(255)",
            "ALTER TABLE applications ADD COLUMN confirmation_id VARCHAR(255)",
            "ALTER TABLE applications ADD COLUMN notes TEXT",
            "ALTER TABLE applications ADD COLUMN follow_up_date VARCHAR(10)",
            "CREATE INDEX IF NOT EXISTS ix_applications_stage ON applications (stage)",
            # Stage 6
            "ALTER TABLE applications ADD COLUMN form_state JSON",
        ]
        for stmt in migrations:
            try:
                await conn.execute(text(stmt))
            except OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise

    # SQLite: WAL lets the dashboard read while a discovery run is writing
    if engine.url.get_backend_name() == "sqlite":
        async with engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")

    await _backfill_dedupe_keys()
    await _backfill_application_stages()


async def _backfill_application_stages() -> None:
    """Give applications created before Stage 5 a lifecycle stage derived from their old status."""
    from sqlalchemy import select
    from backend.database.models import Application
    from backend.services.lifecycle import stage_from_legacy_status

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(Application).where(Application.stage.is_(None)))).scalars().all()
        for app in rows:
            app.stage = stage_from_legacy_status(app.status)
        if rows:
            await session.commit()


async def _backfill_dedupe_keys() -> None:
    """Fill dedupe_key / url_key for jobs stored before Stage 3 (one-off, cheap)."""
    from sqlalchemy import select
    from backend.database.models import Job
    from backend.tools.duplicate_checker import DuplicateChecker

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Job).where((Job.dedupe_key.is_(None)) | ((Job.url_key.is_(None)) & (Job.url.isnot(None))))
        )).scalars().all()
        for job in rows:
            job.dedupe_key = DuplicateChecker.dedupe_key(job.company, job.title, job.location)
            job.url_key = DuplicateChecker.normalize_url(job.url) if job.url else None
        if rows:
            await session.commit()
