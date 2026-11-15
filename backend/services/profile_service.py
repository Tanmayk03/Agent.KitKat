"""
Agent KitKat - Profile Service
Handles retrieval, default initialization, and updates for user career profile.
"""

import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import UserProfile
from backend.schemas.profile import UserProfileUpdate

logger = logging.getLogger("agent_kitkat.profile_service")


class ProfileService:
    """Service for managing the personal profile."""

    @staticmethod
    async def get_or_create_profile(session: AsyncSession) -> UserProfile:
        """
        Retrieve user profile, or create default initialized profile if none exists.
        Default values are based on specification:
        - B.Tech in CS & Data Science, SRM University, Delhi NCR, CGPA 8.44, Graduating May 2027.
        - Preferred roles: Software Engineer Intern, AI/ML Intern, etc.
        - Skills pending verification from resume.
        """
        result = await session.execute(select(UserProfile).order_by(UserProfile.id.asc()))
        profile = result.scalars().first()

        if profile is None:
            logger.info("Initializing default user profile...")
            profile = UserProfile(
                full_name="Tanmay Kapoor",
                email="tanmaykapoor003@gmail.com",
                phone="+91-7905170353",
                location="Delhi NCR, India",
                linkedin_url="https://linkedin.com/in/tanmay-kapoor",
                github_url="https://github.com/tanmayk03",
                portfolio_url="https://tanmayk.tech",
                education={
                    "degree": "B.Tech",
                    "specialization": "Computer Science (Data Science)",
                    "college": "SRM University, Delhi NCR",
                    "cgpa": 8.53,
                    "graduation": "May 2027",
                    "graduation_year": 2027
                },
                preferred_roles=[
                    "Software Engineer Intern",
                    "Software Developer Intern",
                    "Frontend Developer Intern",
                    "Full Stack Developer Intern",
                    "Backend Developer Intern",
                    "AI/ML Intern",
                    "Data Engineer Intern"
                ],
                preferred_locations=[
                    "India",
                    "Remote",
                    "Bangalore",
                    "Noida",
                    "Delhi NCR"
                ],
                expected_stipend="Market Rate / Negotiable",
                work_mode="Any",
                verified_skills=[],
                unverified_skills=[
                    "Python",
                    "JavaScript",
                    "Java",
                    "C++",
                    "SQL",
                    "React.js",
                    "React",
                    "Redux",
                    "Node.js",
                    "Express.js",
                    "FastAPI",
                    "MongoDB",
                    "MySQL",
                    "Docker",
                    "Microsoft Azure",
                    "Tailwind CSS"
                ],
                projects=[],
                work_experience=[],
                certifications=[],
                application_preferences={
                    "daily_search_time": "09:00",
                    "max_applications_per_day": 5,
                    "min_match_score": 75,
                    "submission_policy": "manual_approval",
                    "search_frequency": "once_daily"
                },
                active_resume_id=None
            )
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            logger.info("Default user profile initialized with ID: %s", profile.id)

        return profile

    @staticmethod
    async def update_profile(session: AsyncSession, update_data: UserProfileUpdate) -> UserProfile:
        """Update editable profile fields."""
        profile = await ProfileService.get_or_create_profile(session)

        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        await session.commit()
        await session.refresh(profile)
        logger.info("User profile updated successfully.")
        return profile


# Singleton instance
profile_service = ProfileService()
