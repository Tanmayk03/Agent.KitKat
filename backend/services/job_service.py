"""
Agent KitKat - Job Service
Coordinates URL fetching, raw text analysis, and PDF job description extraction.
Persists opportunities into the local SQLite database.
"""

import os
import uuid
import logging
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import Job
from backend.schemas.job import (
    JobAnalysisResponse,
    ExtractedJobDetails,
    JobListItem
)
from backend.tools.url_reader import URLReader
from backend.tools.resume_parser import ResumeParser
from backend.agents.job_reader import JobReaderAgent

logger = logging.getLogger("agent_kitkat.job_service")
settings = get_settings()


class JobService:
    """Service for handling Mode B manual job analysis and persistence."""

    @staticmethod
    async def analyze_from_url(session: AsyncSession, url: str) -> JobAnalysisResponse:
        """
        Fetch public job posting by URL, parse requirements via JobReaderAgent,
        and save to database. If access is restricted, prompts for manual paste.
        """
        clean_text, error_msg, requires_manual_paste = await URLReader.fetch_job_page(url)

        if requires_manual_paste or not clean_text:
            return JobAnalysisResponse(
                id=str(uuid.uuid4()),
                source="manual_url",
                url=url,
                extracted=ExtractedJobDetails(
                    company_name="Pending Manual Paste",
                    job_title="Pending Manual Paste",
                    job_description=error_msg or "Page inaccessible.",
                    application_url=url
                ),
                raw_text_length=0,
                analysis_duration_ms=0.0,
                requires_manual_paste=True,
                message=error_msg
            )

        return await JobService._process_and_save_job(
            session=session,
            text=clean_text,
            source="manual_url",
            source_url=url
        )

    @staticmethod
    async def analyze_from_text(
        session: AsyncSession,
        text: str,
        title: Optional[str] = None,
        company: Optional[str] = None,
        url: Optional[str] = None
    ) -> JobAnalysisResponse:
        """
        Analyze pasted raw job description text.
        """
        return await JobService._process_and_save_job(
            session=session,
            text=text,
            source="manual_text",
            source_url=url,
            provided_title=title,
            provided_company=company
        )

    @staticmethod
    async def analyze_from_file(
        session: AsyncSession,
        file_name: str,
        file_bytes: bytes
    ) -> JobAnalysisResponse:
        """
        Analyze an uploaded job description document (PDF or DOCX).
        """
        temp_path = os.path.join(settings.STORAGE_DIR, f"temp_{uuid.uuid4()}_{file_name}")
        try:
            with open(temp_path, "wb") as f:
                f.write(file_bytes)

            raw_text = ResumeParser.parse_file(temp_path)
            return await JobService._process_and_save_job(
                session=session,
                text=raw_text,
                source="manual_file"
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    async def _process_and_save_job(
        session: AsyncSession,
        text: str,
        source: str,
        source_url: Optional[str] = None,
        provided_title: Optional[str] = None,
        provided_company: Optional[str] = None
    ) -> JobAnalysisResponse:
        """Internal helper to invoke JobReaderAgent and save Job model."""
        extracted, duration_ms = await JobReaderAgent.analyze_job_text(
            text=text,
            provided_title=provided_title,
            provided_company=provided_company,
            source_url=source_url
        )

        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            company=extracted.company_name,
            title=extracted.job_title,
            description=extracted.job_description,
            location=extracted.work_location,
            work_mode=extracted.work_mode,
            url=source_url,
            source=source,
            job_id_external=extracted.job_id,
            required_degree=extracted.required_degree,
            graduation_eligibility=extracted.graduation_eligibility,
            minimum_cgpa=extracted.minimum_cgpa,
            required_skills=extracted.required_skills,
            experience_required=extracted.experience_requirements,
            salary_stipend=extracted.salary_or_stipend,
            deadline=extracted.application_deadline,
            raw_text=text,
            status="analyzed"
        )

        session.add(job)
        await session.commit()
        await session.refresh(job)

        return JobAnalysisResponse(
            id=job.id,
            source=source,
            url=source_url,
            extracted=extracted,
            raw_text_length=len(text),
            analysis_duration_ms=duration_ms,
            requires_manual_paste=False,
            message="Job description successfully analyzed and stored."
        )

    @staticmethod
    async def list_jobs(session: AsyncSession) -> List[Job]:
        """List all analyzed jobs."""
        result = await session.execute(select(Job).order_by(Job.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_job(session: AsyncSession, job_id: str) -> Optional[Job]:
        """Retrieve single job by ID."""
        result = await session.execute(select(Job).where(Job.id == job_id))
        return result.scalars().first()


# Singleton instance
job_service = JobService()
