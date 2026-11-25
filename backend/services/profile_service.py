"""
Agent KitKat - Profile Service
Handles retrieval, default initialization, and updates for user career profile.
"""

import json
import logging
import os
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import UserProfile
from backend.schemas.profile import UserProfileUpdate

logger = logging.getLogger("agent_kitkat.profile_service")


from backend.config import get_settings

settings = get_settings()

# Non-personal defaults for a brand-new profile. Personal details are NEVER hardcoded:
# fill them in the Profile page, or put them in the git-ignored profile_seed.json
# (see profile_seed.example.json).
DEFAULT_PREFERENCES = {
    "daily_search_time": "09:00",
    "max_applications_per_day": 5,
    "min_match_score": 75,
    "submission_policy": "manual_approval",
    "search_frequency": "once_daily",
    "scheduler_enabled": False,
}
DEFAULT_ROLES = [
    "Software Engineer Intern", "Software Developer Intern", "Backend Developer Intern",
    "Full Stack Developer Intern", "Frontend Developer Intern", "AI/ML Intern",
    "Generative AI Engineer Intern", "Python Developer", "Java Developer", "React Developer",
    "Graduate Engineer Trainee", "Entry-level Software Engineer",
]
DEFAULT_LOCATIONS = ["India", "Remote"]
SEEDABLE_FIELDS = {
    "full_name", "email", "phone", "location", "linkedin_url", "github_url", "portfolio_url",
    "education", "preferred_roles", "preferred_locations", "expected_stipend", "work_mode",
    "unverified_skills", "projects", "work_experience", "certifications",
}


def _load_seed() -> Dict[str, Any]:
    path = settings.PROFILE_SEED_FILE
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if k in SEEDABLE_FIELDS} if isinstance(data, dict) else {}
    except (OSError, ValueError) as e:
        logger.warning("Could not read profile seed file %s: %s", path, e)
        return {}


class ProfileService:
    """Service for managing the personal profile."""

    @staticmethod
    async def get_or_create_profile(session: AsyncSession) -> UserProfile:
        """
        Retrieve the user profile, creating an empty one on first run.
        A new profile is seeded only from the optional, git-ignored profile_seed.json.
        """
        result = await session.execute(select(UserProfile).order_by(UserProfile.id.asc()))
        profile = result.scalars().first()

        if profile is None:
            seed = _load_seed()
            logger.info("Initializing new user profile%s...", " from profile_seed.json" if seed else "")
            profile = UserProfile(
                full_name=seed.get("full_name", ""),
                email=seed.get("email", ""),
                phone=seed.get("phone", ""),
                location=seed.get("location", ""),
                linkedin_url=seed.get("linkedin_url", ""),
                github_url=seed.get("github_url", ""),
                portfolio_url=seed.get("portfolio_url", ""),
                education=seed.get("education", {}),
                preferred_roles=seed.get("preferred_roles", DEFAULT_ROLES),
                preferred_locations=seed.get("preferred_locations", DEFAULT_LOCATIONS),
                expected_stipend=seed.get("expected_stipend", ""),
                work_mode=seed.get("work_mode", "Any"),
                verified_skills=[],  # only a parsed resume can verify skills
                unverified_skills=seed.get("unverified_skills", []),
                projects=seed.get("projects", []),
                work_experience=seed.get("work_experience", []),
                certifications=seed.get("certifications", []),
                application_preferences=dict(DEFAULT_PREFERENCES),
                active_resume_id=None
            )
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            logger.info("User profile initialized with ID: %s", profile.id)

        return profile

    @staticmethod
    async def update_profile(session: AsyncSession, update_data: UserProfileUpdate) -> UserProfile:
        """Update editable profile fields. Preferences are merged, not replaced."""
        profile = await ProfileService.get_or_create_profile(session)

        update_dict = update_data.model_dump(exclude_unset=True)
        if "application_preferences" in update_dict and update_dict["application_preferences"] is not None:
            merged = dict(profile.application_preferences or {})
            incoming = dict(update_dict["application_preferences"])
            # Followed career boards are managed only via /api/discovery/boards, so a stale
            # copy sent back by a settings form can never overwrite them.
            incoming.pop("career_boards", None)
            merged.update(incoming)
            update_dict["application_preferences"] = merged
        if "education" in update_dict and update_dict["education"] is not None:
            merged_edu = dict(profile.education or {})
            merged_edu.update(update_dict["education"])
            update_dict["education"] = merged_edu

        for key, value in update_dict.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        await session.commit()
        await session.refresh(profile)
        logger.info("User profile updated successfully.")
        return profile


# Singleton instance
profile_service = ProfileService()
