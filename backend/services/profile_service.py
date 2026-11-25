"""
Agent KitKat - Profile Service
Handles retrieval, default initialization, and updates for user career profile.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
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
    "unverified_skills", "projects", "work_experience", "certifications", "work_authorized_countries",
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
                work_authorized_countries=seed.get("work_authorized_countries", []),
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


# ---------------------------------------------------------------------------------------------
# Stage 4: profile validation and resume import (with review)
# ---------------------------------------------------------------------------------------------
from backend.tools.resume_profile_extractor import extract_profile_facts, extract_cgpa  # noqa: E402


def _get_field(profile: UserProfile, field: str) -> Any:
    if field.startswith("education."):
        return (profile.education or {}).get(field.split(".", 1)[1])
    return getattr(profile, field, None)


def profile_completeness(profile: UserProfile, active_resume=None) -> Dict[str, Any]:
    """Warnings about missing or inconsistent ground-truth facts. Severity: error | warning | info."""
    warnings = []
    edu = profile.education or {}

    def warn(field, severity, message):
        warnings.append({"field": field, "severity": severity, "message": message})

    for field, label in (("full_name", "Full name"), ("email", "Email"), ("phone", "Phone")):
        if not (getattr(profile, field) or "").strip():
            warn(field, "error", f"{label} is missing: application forms cannot be filled without it.")
    for key, label, why in (
        ("degree", "Degree", "degree requirements"),
        ("graduation_year", "Graduation year", "batch eligibility"),
        ("cgpa", "CGPA", "CGPA cut-offs"),
    ):
        if edu.get(key) in (None, ""):
            warn(f"education.{key}", "error", f"{label} is missing: {why} will show UNKNOWN.")
    if edu.get("active_backlogs") is None:
        warn("education.active_backlogs", "warning", "Active backlogs not provided: 'no backlogs' rules will show UNKNOWN.")
    if not edu.get("college"):
        warn("education.college", "warning", "College / university is missing.")
    if not (profile.work_authorized_countries or []):
        warn("work_authorized_countries", "warning", "Work authorisation not provided (e.g. India): 'authorised to work in…' rules will show UNKNOWN.")
    if not (profile.projects or []):
        warn("projects", "warning", "No projects in your profile: the Projects factor (20%) cannot score anything.")
    if not active_resume:
        warn("active_resume_id", "error", "No active resume: skills cannot be verified and nothing can be uploaded to applications.")
    else:
        if not (profile.verified_skills or []):
            warn("verified_skills", "warning", "No verified skills yet: import them from your resume.")
        found = extract_cgpa(active_resume.raw_text or "")
        if edu.get("cgpa") not in (None, "") and found and abs(float(edu["cgpa"]) - found["value"]) > 0.005:
            warn("education.cgpa", "error",
                 f"Profile CGPA {edu['cgpa']} differs from your active resume ({found['value']}: \"{found['evidence']}\"). Fix whichever is out of date.")
        year = edu.get("graduation_year")
        if year and str(year) not in (active_resume.raw_text or ""):
            warn("education.graduation_year", "info", f"Graduation year {year} does not appear in your active resume text.")
    errors = sum(1 for w in warnings if w["severity"] == "error")
    return {"complete": errors == 0, "error_count": errors, "warnings": warnings}


def resume_suggestions(profile: UserProfile, resume) -> List[Dict[str, Any]]:
    sections = None
    if resume.structured_data:
        sd = resume.structured_data
        sections = {k: sd.get(k) or [] for k in ("education", "experience", "projects", "certifications")}
    out = []
    for s in extract_profile_facts(resume.raw_text or "", sections):
        current = _get_field(profile, s["field"])
        suggested = s["suggested"]
        if s["field"] == "verified_skills":
            current_list = list(current or [])
            new = [x for x in suggested if x not in current_list]
            s["differs"] = bool(new)
            s["note"] = f"{len(new)} new: {', '.join(new[:8])}" if new else "Already verified"
        elif s["field"] == "projects":
            s["differs"] = not current
            s["note"] = "Replaces your current project list" if current else None
        else:
            s["differs"] = str(current or "").strip().lower() != str(suggested).strip().lower()
        s["current"] = current
        out.append(s)
    return out


async def apply_resume_suggestions(session: AsyncSession, profile: UserProfile, resume, fields: List[str]) -> UserProfile:
    """Apply only the suggestions you ticked (recomputed server-side from the resume itself)."""
    chosen = {s["field"]: s for s in resume_suggestions(profile, resume) if s["field"] in set(fields)}
    edu = dict(profile.education or {})
    for field, s in chosen.items():
        val = s["suggested"]
        if field.startswith("education."):
            edu[field.split(".", 1)[1]] = val
        elif field == "verified_skills":
            verified = sorted(set(profile.verified_skills or []) | set(val))
            profile.verified_skills = verified
            profile.unverified_skills = [x for x in (profile.unverified_skills or []) if x not in verified]
        else:
            setattr(profile, field, val)
    profile.education = edu
    await session.commit()
    await session.refresh(profile)
    return profile
