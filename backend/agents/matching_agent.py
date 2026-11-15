"""
Agent KitKat - Resume Matching Agent
Calculates transparent weighted resume compatibility scores against job opportunities.

Category Weights:
- Technical skills: 35%
- Education and graduation: 20%
- Projects and experience: 20%
- Role relevance: 15%
- Location: 10%
Total: 100%

Strict Rule:
Do not allow a high match score to override a mandatory eligibility failure.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.database.models import Job, UserProfile, Resume
from backend.schemas.matching import (
    EligibilityResponse,
    MatchCategoryScores,
    MatchResponse
)
from backend.agents.eligibility_agent import (
    EligibilityAgent,
    SENIOR_ROLE_KEYWORDS,
    INTERN_FRESHER_KEYWORDS,
    INDIA_LOCATION_PATTERNS,
    REMOTE_LOCATION_PATTERNS
)

logger = logging.getLogger("agent_kitkat.matching_agent")


class MatchingAgent:
    """Agent that calculates weighted match scores between resumes/profiles and jobs."""

    @classmethod
    def evaluate_job(
        cls,
        job: Job,
        profile: UserProfile,
        resume: Optional[Resume] = None
    ) -> MatchResponse:
        """
        Executes eligibility checks and calculates weighted resume matching score.
        """
        # Step 1: Run deterministic eligibility verification
        eligibility: EligibilityResponse = EligibilityAgent.verify_eligibility(job, profile)

        # Step 2: Extract candidate skills (from profile and active resume)
        candidate_skills_set = set(s.lower() for s in (profile.verified_skills or []))
        if resume and resume.structured_data:
            resume_skills = resume.structured_data.get("extracted_skills", [])
            for s in resume_skills:
                candidate_skills_set.add(s.lower())

        # -------------------------------------------------------------
        # Category 1: Technical Skills (Weight: 35%)
        # -------------------------------------------------------------
        job_skills = job.required_skills or []
        matching_skills: List[str] = []
        missing_skills: List[str] = []

        if not job_skills:
            # If no specific skills stated, give standard baseline
            tech_score = 30.0
        else:
            for skill in job_skills:
                if skill.lower() in candidate_skills_set:
                    matching_skills.append(skill)
                else:
                    missing_skills.append(skill)

            match_ratio = len(matching_skills) / len(job_skills)
            tech_score = round(match_ratio * 35.0, 2)

        # -------------------------------------------------------------
        # Category 2: Education & Graduation (Weight: 20%)
        # -------------------------------------------------------------
        if eligibility.degree.status == "PASS" and eligibility.graduation.status == "PASS":
            edu_score = 20.0
        elif eligibility.degree.status == "PASS" and eligibility.graduation.status == "UNKNOWN":
            edu_score = 15.0
        elif eligibility.degree.status == "UNKNOWN" and eligibility.graduation.status == "PASS":
            edu_score = 14.0
        elif eligibility.degree.status == "FAIL" or eligibility.graduation.status == "FAIL":
            edu_score = 0.0
        else:
            edu_score = 10.0

        # -------------------------------------------------------------
        # Category 3: Projects & Experience (Weight: 20%)
        # -------------------------------------------------------------
        relevant_projects: List[str] = []
        candidate_projects = profile.projects or []
        if resume and resume.structured_data:
            for proj in resume.structured_data.get("projects", []):
                if isinstance(proj, str) and len(proj) > 5:
                    relevant_projects.append(proj)

        # Score based on projects present and tech keyword alignment
        if relevant_projects or candidate_projects:
            proj_score = 16.0
            # Check if any project mentions matching skills
            job_text_lower = (job.description or "").lower()
            if any(s.lower() in job_text_lower for s in matching_skills):
                proj_score = 20.0
        else:
            # Base credit for having verified portfolio skills
            proj_score = 10.0

        # -------------------------------------------------------------
        # Category 4: Role Relevance (Weight: 15%)
        # -------------------------------------------------------------
        job_title_lower = (job.title or "").lower()
        preferred_roles = [r.lower() for r in (profile.preferred_roles or [])]

        is_senior = any(re.search(pat, job_title_lower) for pat in SENIOR_ROLE_KEYWORDS)
        is_intern_or_fresher = any(re.search(pat, job_title_lower) for pat in INTERN_FRESHER_KEYWORDS)

        if is_senior:
            # Senior/Lead/Staff role completely mismatches candidate intern profile
            role_score = 0.0
        elif any(pref in job_title_lower for pref in preferred_roles):
            role_score = 15.0
        elif is_intern_or_fresher and any(k in job_title_lower for k in ["software", "developer", "engineer", "frontend", "backend", "full stack", "ai", "ml", "data"]):
            role_score = 15.0
        elif is_intern_or_fresher:
            role_score = 12.0
        elif any(k in job_title_lower for k in ["software", "developer", "engineer"]):
            # Generic engineering role without intern specification
            role_score = 5.0
        else:
            role_score = 2.0

        # -------------------------------------------------------------
        # Category 5: Location & Work Mode (Weight: 10%)
        # User constraint: Priority to India jobs; foreign jobs ONLY if Remote.
        # -------------------------------------------------------------
        job_loc_lower = (job.location or "").lower()
        job_mode_lower = (job.work_mode or "Unknown").lower()
        is_in_india = (
            any(re.search(pat, job_loc_lower) for pat in INDIA_LOCATION_PATTERNS)
            or any(re.search(pat, (job.raw_text or "").lower()[:500]) for pat in INDIA_LOCATION_PATTERNS)
        )
        is_remote = (
            job_mode_lower == "remote"
            or any(re.search(pat, job_loc_lower) for pat in REMOTE_LOCATION_PATTERNS)
            or any(re.search(pat, (job.work_mode or "").lower()) for pat in REMOTE_LOCATION_PATTERNS)
        )

        if eligibility.location.status == "FAIL":
            loc_score = 0.0
        elif is_in_india:
            # Top priority score (10.0/10) for domestic India opportunities
            loc_score = 10.0
        elif is_remote:
            # High priority score (9.0/10) for international remote positions
            loc_score = 9.0
        else:
            loc_score = 0.0

        # -------------------------------------------------------------
        # Overall Weighted Score Calculation
        # -------------------------------------------------------------
        overall_score = round(tech_score + edu_score + proj_score + role_score + loc_score, 1)
        # Cap strictly between 0 and 100
        overall_score = max(0.0, min(100.0, overall_score))

        category_scores = MatchCategoryScores(
            technical_skills=tech_score,
            education_and_graduation=edu_score,
            projects_and_experience=proj_score,
            role_relevance=role_score,
            location=loc_score
        )

        # -------------------------------------------------------------
        # Recommendation Logic (Strict Override Rules)
        # -------------------------------------------------------------
        if eligibility.overall_status == "FAIL" or is_senior:
            recommendation = "INELIGIBLE"
        elif eligibility.overall_status == "UNKNOWN":
            if overall_score >= 70.0 and is_intern_or_fresher:
                recommendation = "CONSIDER_WITH_VERIFICATION"
            else:
                recommendation = "NEEDS_VERIFICATION"
        else:
            # India roles given strong recommendation boost when qualified
            if is_in_india and overall_score >= 75.0 and is_intern_or_fresher:
                recommendation = "STRONGLY_RECOMMENDED"
            elif overall_score >= 80.0 and is_intern_or_fresher:
                recommendation = "STRONGLY_RECOMMENDED"
            elif overall_score >= 65.0 and is_intern_or_fresher:
                recommendation = "RECOMMENDED"
            elif overall_score >= 50.0:
                recommendation = "CONSIDER"
            else:
                recommendation = "NOT_RECOMMENDED"

        # -------------------------------------------------------------
        # Transparent Explanation
        # -------------------------------------------------------------
        explanation = (
            f"Overall Match Score: {overall_score}% | Status: {eligibility.overall_status} | Recommendation: {recommendation}\n"
            f"- Technical Skills ({tech_score}/35): Matched {len(matching_skills)} of {len(job_skills)} required skills.\n"
            f"- Education & Graduation ({edu_score}/20): {eligibility.graduation.details}\n"
            f"- Projects & Experience ({proj_score}/20): Assessed against candidate portfolio and resume experience.\n"
            f"- Role Relevance ({role_score}/15): '{job.title}' compared with preferred intern roles.\n"
            f"- Location & Mode ({loc_score}/10): {eligibility.location.details} ({job.work_mode})"
        )
        if eligibility.rejection_reasons:
            explanation += "\nHard Rejection Reasons: " + " | ".join(eligibility.rejection_reasons)
        if eligibility.unverified_requirements:
            explanation += "\nPending Verification: " + " | ".join(eligibility.unverified_requirements)

        return MatchResponse(
            job_id=job.id,
            resume_id=resume.id if resume else None,
            overall_score=overall_score,
            category_scores=category_scores,
            matching_skills=matching_skills,
            missing_skills=missing_skills,
            relevant_projects=relevant_projects,
            recommendation=recommendation,
            explanation=explanation,
            eligibility=eligibility
        )
