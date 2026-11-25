"""
Agent KitKat - Matching Service
Coordinates eligibility evaluation, resume scoring, database persistence,
and job prioritization rankings.
"""

import uuid
import logging
from typing import List, Optional, Tuple
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Job, UserProfile, Resume, EligibilityResult, MatchResult
from backend.schemas.matching import (
    MatchResponse,
    EligibilityResponse,
    MatchCategoryScores,
    RequirementCheck,
    JobRankingItem
)
from backend.services.profile_service import ProfileService
from backend.services.resume_service import ResumeService
from backend.agents.matching_agent import MatchingAgent

logger = logging.getLogger("agent_kitkat.matching_service")


class MatchingService:
    """Service handling job eligibility checks, resume matching, and rankings."""

    @staticmethod
    async def evaluate_job(
        session: AsyncSession,
        job_id: str,
        resume_id: Optional[str] = None
    ) -> MatchResponse:
        """
        Evaluates a job against candidate profile and active/selected resume.
        Saves EligibilityResult and MatchResult to SQLite.
        """
        # Fetch Job
        job_res = await session.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalars().first()
        if not job:
            raise ValueError(f"Job with ID '{job_id}' not found.")

        # Fetch Profile
        profile = await ProfileService.get_or_create_profile(session)

        # Fetch Resume
        target_resume_id = resume_id or profile.active_resume_id
        resume = None
        if target_resume_id:
            resume = await ResumeService.get_resume(session, target_resume_id)

        # Execute evaluation via MatchingAgent
        min_score = float((profile.application_preferences or {}).get("min_match_score", 75))
        match_resp: MatchResponse = MatchingAgent.evaluate_job(
            job=job,
            profile=profile,
            resume=resume,
            min_score=min_score,
        )

        # ---------------------------------------------------------
        # Persist EligibilityResult
        # ---------------------------------------------------------
        el = match_resp.eligibility
        existing_el_res = await session.execute(
            select(EligibilityResult).where(EligibilityResult.job_id == job.id)
        )
        existing_el = existing_el_res.scalars().first()

        if existing_el:
            existing_el.overall_status = el.overall_status
            existing_el.degree_status = el.degree.status
            existing_el.degree_details = el.degree.details
            existing_el.graduation_status = el.graduation.status
            existing_el.graduation_details = el.graduation.details
            existing_el.cgpa_status = el.cgpa.status
            existing_el.cgpa_details = el.cgpa.details
            existing_el.location_status = el.location.status
            existing_el.location_details = el.location.details
            existing_el.work_mode_status = el.work_mode.status
            existing_el.work_mode_details = el.work_mode.details
            existing_el.experience_status = el.experience_level.status if el.experience_level else None
            existing_el.experience_details = el.experience_level.details if el.experience_level else None
            existing_el.checks_json = el.model_dump(mode="json")
            existing_el.rejection_reasons = el.rejection_reasons
            existing_el.unverified_requirements = el.unverified_requirements
        else:
            new_el = EligibilityResult(
                id=str(uuid.uuid4()),
                job_id=job.id,
                overall_status=el.overall_status,
                degree_status=el.degree.status,
                degree_details=el.degree.details,
                graduation_status=el.graduation.status,
                graduation_details=el.graduation.details,
                cgpa_status=el.cgpa.status,
                cgpa_details=el.cgpa.details,
                location_status=el.location.status,
                location_details=el.location.details,
                work_mode_status=el.work_mode.status,
                work_mode_details=el.work_mode.details,
                experience_status=el.experience_level.status if el.experience_level else None,
                experience_details=el.experience_level.details if el.experience_level else None,
                rejection_reasons=el.rejection_reasons,
                unverified_requirements=el.unverified_requirements,
                checks_json=el.model_dump(mode="json"),
            )
            session.add(new_el)

        # ---------------------------------------------------------
        # Persist MatchResult
        # ---------------------------------------------------------
        cats = match_resp.category_scores
        existing_mr_res = await session.execute(
            select(MatchResult).where(MatchResult.job_id == job.id)
        )
        existing_mr = existing_mr_res.scalars().first()

        if existing_mr:
            existing_mr.resume_id = resume.id if resume else None
            existing_mr.overall_score = match_resp.overall_score
            existing_mr.technical_skills_score = cats.technical_skills
            existing_mr.education_score = cats.education_and_graduation
            existing_mr.projects_score = cats.projects_and_experience
            existing_mr.role_relevance_score = cats.role_relevance
            existing_mr.location_score = cats.location
            existing_mr.matching_skills = match_resp.matching_skills
            existing_mr.missing_skills = match_resp.missing_skills
            existing_mr.relevant_projects = match_resp.relevant_projects
            existing_mr.recommendation = match_resp.recommendation
            existing_mr.explanation = match_resp.explanation
            existing_mr.details_json = {"factor_explanations": match_resp.factor_explanations,
                                        "na_factors": match_resp.na_factors, "next_action": match_resp.next_action}
        else:
            new_mr = MatchResult(
                id=str(uuid.uuid4()),
                job_id=job.id,
                resume_id=resume.id if resume else None,
                overall_score=match_resp.overall_score,
                technical_skills_score=cats.technical_skills,
                education_score=cats.education_and_graduation,
                projects_score=cats.projects_and_experience,
                role_relevance_score=cats.role_relevance,
                location_score=cats.location,
                matching_skills=match_resp.matching_skills,
                missing_skills=match_resp.missing_skills,
                relevant_projects=match_resp.relevant_projects,
                recommendation=match_resp.recommendation,
                explanation=match_resp.explanation,
                details_json={"factor_explanations": match_resp.factor_explanations,
                              "na_factors": match_resp.na_factors, "next_action": match_resp.next_action},
            )
            session.add(new_mr)

        # ---------------------------------------------------------
        # Update Job Workflow Status
        # ---------------------------------------------------------
        if el.overall_status == "FAIL":
            job.status = "rejected"
        elif match_resp.overall_score >= min_score and el.overall_status == "PASS":
            job.status = "shortlisted"
        else:
            job.status = "analyzed"

        await session.commit()
        logger.info(
            "Job '%s' at '%s' evaluated: Score=%.1f%%, Eligibility=%s, Recommendation=%s",
            job.title, job.company, match_resp.overall_score, el.overall_status, match_resp.recommendation
        )

        return match_resp

    @staticmethod
    async def get_evaluation(session: AsyncSession, job_id: str) -> Optional[MatchResponse]:
        """Retrieve stored evaluation, or compute if not yet evaluated."""
        mr_res = await session.execute(select(MatchResult).where(MatchResult.job_id == job_id))
        mr = mr_res.scalars().first()

        el_res = await session.execute(select(EligibilityResult).where(EligibilityResult.job_id == job_id))
        el = el_res.scalars().first()

        if not mr or not el:
            # Auto-compute if missing
            return await MatchingService.evaluate_job(session, job_id)

        if el.checks_json:
            eligibility_response = EligibilityResponse(**el.checks_json)
        else:
            eligibility_response = None
        eligibility_response = eligibility_response or EligibilityResponse(
            job_id=el.job_id,
            overall_status=el.overall_status,
            degree=RequirementCheck(status=el.degree_status, details=el.degree_details),
            graduation=RequirementCheck(status=el.graduation_status, details=el.graduation_details),
            cgpa=RequirementCheck(status=el.cgpa_status, details=el.cgpa_details),
            location=RequirementCheck(status=el.location_status, details=el.location_details),
            work_mode=RequirementCheck(status=el.work_mode_status, details=el.work_mode_details),
            experience_level=RequirementCheck(status=el.experience_status, details=el.experience_details or "")
            if el.experience_status else None,
            rejection_reasons=el.rejection_reasons or [],
            unverified_requirements=el.unverified_requirements or []
        )

        category_scores = MatchCategoryScores(
            technical_skills=mr.technical_skills_score,
            education_and_graduation=mr.education_score,
            projects_and_experience=mr.projects_score,
            role_relevance=mr.role_relevance_score,
            location=mr.location_score
        )

        return MatchResponse(
            job_id=mr.job_id,
            resume_id=mr.resume_id,
            overall_score=mr.overall_score,
            category_scores=category_scores,
            matching_skills=mr.matching_skills or [],
            missing_skills=mr.missing_skills or [],
            relevant_projects=mr.relevant_projects or [],
            recommendation=mr.recommendation,
            explanation=mr.explanation,
            factor_explanations=(mr.details_json or {}).get("factor_explanations", {}),
            na_factors=(mr.details_json or {}).get("na_factors", []),
            next_action=(mr.details_json or {}).get("next_action"),
            eligibility=eligibility_response
        )

    @staticmethod
    async def list_rankings(session: AsyncSession) -> List[JobRankingItem]:
        """
        Rank all evaluated jobs by overall match score descending.
        Shows eligible and shortlisted jobs at the top.
        """
        query = (
            select(Job, MatchResult, EligibilityResult)
            .join(MatchResult, Job.id == MatchResult.job_id)
            .join(EligibilityResult, Job.id == EligibilityResult.job_id)
            .order_by(desc(MatchResult.overall_score))
        )
        result = await session.execute(query)
        # Hard eligibility outranks score: PASS first, then UNKNOWN (needs verification), then FAIL.
        tier = {"PASS": 0, "UNKNOWN": 1, "FAIL": 2}
        rows = sorted(result.all(), key=lambda r: (tier.get(r[2].overall_status, 1), -(r[1].overall_score or 0)))

        rankings: List[JobRankingItem] = []
        for job, mr, el in rows:
            rankings.append(
                JobRankingItem(
                    job_id=job.id,
                    company=job.company,
                    title=job.title,
                    location=job.location,
                    work_mode=job.work_mode,
                    overall_score=mr.overall_score,
                    eligibility_status=el.overall_status,
                    recommendation=mr.recommendation,
                    matching_skills_count=len(mr.matching_skills or []),
                    missing_skills_count=len(mr.missing_skills or []),
                    created_at=job.created_at
                )
            )

        return rankings


# Singleton instance
matching_service = MatchingService()
