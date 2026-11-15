"""
Agent KitKat - Resume Management Service
Handles upload, local persistence, parsing, skill extraction, and activation of resumes.
"""

import os
import uuid
import logging
from typing import List, Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import Resume, UserProfile
from backend.services.profile_service import ProfileService
from backend.tools.resume_parser import ResumeParser

logger = logging.getLogger("agent_kitkat.resume_service")
settings = get_settings()


class ResumeService:
    """Service for managing uploaded resumes and synchronizing skills with profile."""

    @staticmethod
    async def save_and_parse_resume(
        session: AsyncSession,
        file_name: str,
        file_bytes: bytes
    ) -> Tuple[Resume, UserProfile, List[str]]:
        """
        Save resume locally in storage/resumes, parse text, extract skills,
        and cross-verify against user profile unverified skills.
        """
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in [".pdf", ".docx"]:
            raise ValueError(f"Unsupported file format: {ext}. Only PDF and DOCX files are allowed.")

        # Ensure storage directory exists
        os.makedirs(settings.RESUMES_DIR, exist_ok=True)

        resume_id = str(uuid.uuid4())
        safe_filename = f"{resume_id}_{file_name.replace(' ', '_')}"
        file_path = os.path.join(settings.RESUMES_DIR, safe_filename)

        # Write file securely to disk
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        file_size = len(file_bytes)

        # Parse text and segment sections
        raw_text = ResumeParser.parse_file(file_path)
        sections = ResumeParser.segment_sections(raw_text)
        extracted_skills = ResumeParser.extract_skills(raw_text)

        structured_data = {
            "extracted_skills": extracted_skills,
            "education": sections.get("education", []),
            "projects": sections.get("projects", []),
            "experience": sections.get("experience", []),
            "certifications": sections.get("certifications", [])
        }

        # Check existing resumes to see if this should be active by default
        existing_resumes_res = await session.execute(select(Resume))
        has_resumes = len(existing_resumes_res.scalars().all()) > 0
        is_active = not has_resumes  # First resume is automatically active

        # Create Resume database record
        resume = Resume(
            id=resume_id,
            file_name=file_name,
            file_path=file_path,
            file_type=ext.replace(".", ""),
            file_size_bytes=file_size,
            raw_text=raw_text,
            structured_data=structured_data,
            is_active=is_active
        )
        session.add(resume)

        # Cross-verify profile skills
        profile = await ProfileService.get_or_create_profile(session)
        verified, unverified, all_skills = ResumeParser.verify_profile_skills(
            resume_text=raw_text,
            current_verified=profile.verified_skills or [],
            current_unverified=profile.unverified_skills or []
        )

        profile.verified_skills = verified
        profile.unverified_skills = unverified
        if is_active:
            profile.active_resume_id = resume_id

        await session.commit()
        await session.refresh(resume)
        await session.refresh(profile)

        logger.info(
            "Resume %s (%s) saved and parsed. Verified %d skills, %d remaining unverified.",
            file_name, resume_id, len(verified), len(unverified)
        )

        return resume, profile, all_skills

    @staticmethod
    async def list_resumes(session: AsyncSession) -> List[Resume]:
        """List all resumes ordered by upload date descending."""
        result = await session.execute(select(Resume).order_by(Resume.uploaded_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_resume(session: AsyncSession, resume_id: str) -> Optional[Resume]:
        """Get resume by ID."""
        result = await session.execute(select(Resume).where(Resume.id == resume_id))
        return result.scalars().first()

    @staticmethod
    async def get_active_resume(session: AsyncSession) -> Optional[Resume]:
        """Get the currently active resume."""
        result = await session.execute(select(Resume).where(Resume.is_active == True))
        return result.scalars().first()

    @staticmethod
    async def set_active_resume(session: AsyncSession, resume_id: str) -> Tuple[Resume, UserProfile]:
        """Set a specific resume as active and deactivate all others."""
        target_resume = await ResumeService.get_resume(session, resume_id)
        if not target_resume:
            raise ValueError(f"Resume with ID '{resume_id}' not found.")

        # Deactivate all
        await session.execute(update(Resume).values(is_active=False))

        # Activate target
        target_resume.is_active = True

        # Update profile
        profile = await ProfileService.get_or_create_profile(session)
        profile.active_resume_id = resume_id

        await session.commit()
        await session.refresh(target_resume)
        await session.refresh(profile)

        return target_resume, profile

    @staticmethod
    async def delete_resume(session: AsyncSession, resume_id: str) -> bool:
        """Delete resume record and remove file from disk."""
        resume = await ResumeService.get_resume(session, resume_id)
        if not resume:
            return False

        # Remove file from disk if it exists
        if os.path.exists(resume.file_path):
            try:
                os.remove(resume.file_path)
            except OSError as e:
                logger.warning("Could not delete file %s: %s", resume.file_path, str(e))

        # Update profile if active resume was deleted
        profile = await ProfileService.get_or_create_profile(session)
        if profile.active_resume_id == resume_id:
            profile.active_resume_id = None

        await session.delete(resume)
        await session.commit()
        return True


# Singleton instance
resume_service = ResumeService()
