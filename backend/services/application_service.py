"""
Agent KitKat - Application Preparation Service
Coordinates tailored cover letter generation, screening answers,
field mapping, approval workflows, and submission policies.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    Job,
    UserProfile,
    Resume,
    ApplicationDraft,
    ApprovalRequest,
    Application,
    MatchResult,
    EligibilityResult
)
from backend.schemas.application import (
    ApplicationDraftResponse,
    DraftUpdateRequest,
    ApprovalRequestItem,
    ApplicationTrackerItem
)
from backend.services.profile_service import ProfileService
from backend.services.resume_service import ResumeService
from backend.services.matching_service import MatchingService
from backend.agents.application_agent import ApplicationAgent

logger = logging.getLogger("agent_kitkat.application_service")

# Application states after which a draft must never be regenerated or resubmitted
FINAL_APPLICATION_STATES = {"submitted", "submission_unverified", "application_confirmed", "submission_uncertain"}


class ApplicationConflictError(ValueError):
    """Raised when an action would overwrite or duplicate an already-submitted application."""


class ApplicationService:
    """Service managing application preparation, approval workflow, and tracker records."""

    @staticmethod
    async def prepare_application(
        session: AsyncSession,
        job_id: str,
        resume_id: Optional[str] = None,
        policy_override: Optional[str] = None
    ) -> ApplicationDraftResponse:
        """
        Prepares a complete application draft:
        1. Ensures eligibility & matching results are computed.
        2. Drafts tailored cover letter grounded on verified profile.
        3. Drafts standard answers to screening questions.
        4. Maps verified personal profile to ATS form fields.
        5. Identifies unanswered questions requiring human confirmation.
        6. Enforces submission policy (Manual Approval, Pre-authorized, Prepare Only).
        """
        # Fetch Job
        job_res = await session.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalars().first()
        if not job:
            raise ValueError(f"Job with ID '{job_id}' not found.")

        # Never regenerate a draft for an application that has already been sent
        existing_app_res = await session.execute(select(Application).where(Application.job_id == job_id))
        for existing in existing_app_res.scalars().all():
            if existing.status in FINAL_APPLICATION_STATES:
                raise ApplicationConflictError(
                    f"An application for this job was already sent (status: {existing.status}). "
                    "It will not be regenerated."
                )

        # Fetch Profile
        profile = await ProfileService.get_or_create_profile(session)

        # Get or compute match evaluation
        match_eval = await MatchingService.get_evaluation(session, job_id)
        if not match_eval:
            match_eval = await MatchingService.evaluate_job(session, job_id, resume_id)

        target_resume_id = resume_id or profile.active_resume_id
        resume = None
        if target_resume_id:
            resume = await ResumeService.get_resume(session, target_resume_id)

        # 1. Generate Cover Letter
        cover_letter = await ApplicationAgent.generate_cover_letter(
            job=job,
            profile=profile,
            matching_skills=match_eval.matching_skills
        )

        # 2. Prepare Answers
        custom_answers = await ApplicationAgent.prepare_application_answers(
            job=job,
            profile=profile,
            matching_skills=match_eval.matching_skills
        )

        # 3. Map Form Fields
        form_fields = ApplicationAgent.map_form_fields(profile)

        # 4. Identify Unanswered Questions
        unanswered = ApplicationAgent.identify_unanswered_questions(profile, form_fields, custom_answers)

        # 5. Determine Submission Policy
        user_prefs = profile.application_preferences or {}
        policy = policy_override or user_prefs.get("submission_policy", "manual_approval")
        min_score = user_prefs.get("min_match_score", 75)

        # Status determination. Every submission needs an explicit, per-application human approval,
        # so the legacy "pre_authorized" policy is treated exactly like manual approval.
        if policy == "prepare_only":
            draft_status = "drafted"
            approval_status = None
        else:
            if policy == "pre_authorized":
                logger.info("Policy 'pre_authorized' is disabled for safety; queuing for manual approval.")
            policy = "manual_approval"
            draft_status = "pending_approval"
            approval_status = "pending"

        # -------------------------------------------------------------
        # Create or Update ApplicationDraft
        # -------------------------------------------------------------
        draft_res = await session.execute(
            select(ApplicationDraft).where(ApplicationDraft.job_id == job.id)
        )
        existing_draft = draft_res.scalars().first()

        if existing_draft:
            existing_draft.resume_id = target_resume_id
            existing_draft.cover_letter = cover_letter
            existing_draft.custom_answers = custom_answers
            existing_draft.form_field_values = form_fields
            existing_draft.unanswered_questions = unanswered
            existing_draft.status = draft_status
            draft = existing_draft
        else:
            draft = ApplicationDraft(
                id=str(uuid.uuid4()),
                job_id=job.id,
                resume_id=target_resume_id,
                cover_letter=cover_letter,
                custom_answers=custom_answers,
                form_field_values=form_fields,
                unanswered_questions=unanswered,
                status=draft_status
            )
            session.add(draft)

        await session.flush()

        # -------------------------------------------------------------
        # Create or Update ApprovalRequest if needed
        # -------------------------------------------------------------
        if approval_status:
            appr_res = await session.execute(
                select(ApprovalRequest).where(ApprovalRequest.draft_id == draft.id)
            )
            existing_appr = appr_res.scalars().first()

            if existing_appr:
                existing_appr.status = approval_status
                existing_appr.policy_applied = policy
            else:
                new_appr = ApprovalRequest(
                    id=str(uuid.uuid4()),
                    job_id=job.id,
                    draft_id=draft.id,
                    status=approval_status,
                    policy_applied=policy
                )
                session.add(new_appr)

        # -------------------------------------------------------------
        # Create or Update Application Tracker Record
        # -------------------------------------------------------------
        app_res = await session.execute(
            select(Application).where(Application.job_id == job.id)
        )
        existing_app = app_res.scalars().first()

        if existing_app:
            existing_app.draft_id = draft.id
            existing_app.status = "draft_ready" if draft_status == "drafted" else "awaiting_approval"
        else:
            new_app = Application(
                id=str(uuid.uuid4()),
                job_id=job.id,
                draft_id=draft.id,
                status="draft_ready" if draft_status == "drafted" else "awaiting_approval",
                submission_method="manual"
            )
            session.add(new_app)

        await session.commit()
        await session.refresh(draft)

        return ApplicationDraftResponse(
            id=draft.id,
            job_id=job.id,
            company=job.company,
            role=job.title,
            resume_id=draft.resume_id,
            cover_letter=draft.cover_letter,
            custom_answers=draft.custom_answers or {},
            form_field_values=draft.form_field_values or {},
            unanswered_questions=draft.unanswered_questions or [],
            status=draft.status,
            policy_applied=policy,
            created_at=draft.created_at
        )

    @staticmethod
    async def get_draft(session: AsyncSession, draft_id: str) -> Optional[ApplicationDraftResponse]:
        """Fetch draft by ID."""
        query = (
            select(ApplicationDraft, Job)
            .join(Job, ApplicationDraft.job_id == Job.id)
            .where(ApplicationDraft.id == draft_id)
        )
        res = await session.execute(query)
        row = res.first()
        if not row:
            return None

        draft, job = row
        appr_res = await session.execute(select(ApprovalRequest.policy_applied).where(ApprovalRequest.draft_id == draft.id))
        policy_applied = appr_res.scalars().first() or "prepare_only"
        return ApplicationDraftResponse(
            id=draft.id,
            job_id=job.id,
            company=job.company,
            role=job.title,
            resume_id=draft.resume_id,
            cover_letter=draft.cover_letter,
            custom_answers=draft.custom_answers or {},
            form_field_values=draft.form_field_values or {},
            unanswered_questions=draft.unanswered_questions or [],
            status=draft.status,
            policy_applied=policy_applied,
            created_at=draft.created_at
        )

    @staticmethod
    async def update_draft(
        session: AsyncSession,
        draft_id: str,
        update_data: DraftUpdateRequest
    ) -> ApplicationDraftResponse:
        """Edit drafted cover letter, custom answers, or mapped fields."""
        draft_res = await session.execute(
            select(ApplicationDraft).where(ApplicationDraft.id == draft_id)
        )
        draft = draft_res.scalars().first()
        if not draft:
            raise ValueError(f"Draft with ID '{draft_id}' not found.")
        if draft.status in FINAL_APPLICATION_STATES:
            raise ApplicationConflictError("This application was already sent; its draft can no longer be edited.")

        if update_data.cover_letter is not None:
            draft.cover_letter = update_data.cover_letter
        if update_data.custom_answers is not None:
            draft.custom_answers = update_data.custom_answers
        if update_data.form_field_values is not None:
            draft.form_field_values = update_data.form_field_values

        await session.commit()
        await session.refresh(draft)

        return await ApplicationService.get_draft(session, draft.id)

    @staticmethod
    async def list_approvals(session: AsyncSession) -> List[ApprovalRequestItem]:
        """List all pending approval requests."""
        query = (
            select(ApprovalRequest, Job, ApplicationDraft, MatchResult, EligibilityResult)
            .join(Job, ApprovalRequest.job_id == Job.id)
            .join(ApplicationDraft, ApprovalRequest.draft_id == ApplicationDraft.id)
            .outerjoin(MatchResult, Job.id == MatchResult.job_id)
            .outerjoin(EligibilityResult, Job.id == EligibilityResult.job_id)
            .where(ApprovalRequest.status == "pending")
            .order_by(desc(ApprovalRequest.created_at))
        )
        res = await session.execute(query)
        rows = res.all()

        items = []
        for appr, job, draft, mr, el in rows:
            draft_resp = ApplicationDraftResponse(
                id=draft.id,
                job_id=job.id,
                company=job.company,
                role=job.title,
                resume_id=draft.resume_id,
                cover_letter=draft.cover_letter,
                custom_answers=draft.custom_answers or {},
                form_field_values=draft.form_field_values or {},
                unanswered_questions=draft.unanswered_questions or [],
                status=draft.status,
                policy_applied=appr.policy_applied,
                created_at=draft.created_at
            )
            items.append(
                ApprovalRequestItem(
                    id=appr.id,
                    job_id=job.id,
                    draft_id=draft.id,
                    company=job.company,
                    role=job.title,
                    company_name=job.company,
                    job_title=job.title,
                    job_url=job.url,
                    match_score=mr.overall_score if mr else 0.0,
                    eligibility_status=el.overall_status if el else "UNKNOWN",
                    policy_applied=appr.policy_applied,
                    status=appr.status,
                    created_at=appr.created_at,
                    draft=draft_resp
                )
            )

        return items

    @staticmethod
    async def decide_approval(
        session: AsyncSession,
        approval_id: str,
        action: str,
        decision_notes: Optional[str] = None
    ) -> ApprovalRequestItem:
        """Approve or reject a pending application draft."""
        appr_res = await session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        )
        appr = appr_res.scalars().first()
        if not appr:
            raise ValueError(f"Approval request '{approval_id}' not found.")

        # Fetch draft and application
        draft_res = await session.execute(
            select(ApplicationDraft).where(ApplicationDraft.id == appr.draft_id)
        )
        draft = draft_res.scalars().first()

        app_res = await session.execute(
            select(Application).where(Application.draft_id == appr.draft_id)
        )
        application = app_res.scalars().first()

        # Update decision
        appr.decided_at = datetime.utcnow()
        appr.decision_notes = decision_notes

        if appr.status != "pending":
            raise ApplicationConflictError(f"This approval request was already decided ({appr.status}).")

        if action == "approve":
            appr.status = "approved"
            if draft:
                draft.status = "approved"
            if application:
                application.status = "approved"
        elif action == "reject":
            appr.status = "rejected"
            if draft:
                draft.status = "rejected"
            if application:
                application.status = "withdrawn"
        else:
            raise ValueError(f"Unknown action '{action}'. Use 'approve' or 'reject'.")

        await session.commit()
        await session.refresh(appr)

        # Get job details
        job_res = await session.execute(select(Job).where(Job.id == appr.job_id))
        job = job_res.scalars().first()

        return ApprovalRequestItem(
            id=appr.id,
            job_id=appr.job_id,
            draft_id=appr.draft_id,
            company=job.company if job else "Unknown",
            role=job.title if job else "Unknown",
            match_score=0.0,
            eligibility_status="UNKNOWN",
            policy_applied=appr.policy_applied,
            status=appr.status,
            created_at=appr.created_at
        )

    @staticmethod
    async def list_applications(session: AsyncSession) -> List[ApplicationTrackerItem]:
        """List all tracked applications."""
        query = (
            select(Application, Job, MatchResult, ApprovalRequest.status)
            .join(Job, Application.job_id == Job.id)
            .outerjoin(MatchResult, Job.id == MatchResult.job_id)
            .outerjoin(ApprovalRequest, ApprovalRequest.draft_id == Application.draft_id)
            .order_by(desc(Application.created_at))
        )
        res = await session.execute(query)
        rows = res.all()

        items = []
        for app_rec, job, mr, approval_status in rows:
            items.append(
                ApplicationTrackerItem(
                    id=app_rec.id,
                    application_id=app_rec.id,
                    job_id=job.id,
                    draft_id=app_rec.draft_id,
                    company=job.company,
                    role=job.title,
                    company_name=job.company,
                    job_title=job.title,
                    job_url=job.url,
                    status=app_rec.status,
                    approval_status=approval_status,
                    match_score=mr.overall_score if mr else None,
                    submission_method=app_rec.submission_method,
                    submission_result=app_rec.submission_result,
                    failure_reason=app_rec.failure_reason,
                    applied_at=app_rec.applied_at,
                    updated_at=getattr(app_rec, "updated_at", app_rec.created_at),
                    created_at=app_rec.created_at
                )
            )

        return items


# Singleton instance
application_service = ApplicationService()

