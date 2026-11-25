"""
Agent KitKat - Browser Automation Service
Coordinates Playwright automation with database state, draft data,
active candidate resume, and application tracking records.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from backend.database.models import Job, Resume, ApplicationDraft, Application, ApprovalRequest
from backend.agents.browser_agent import browser_agent
from backend.schemas.browser import BrowserRunResult, EmergencyStopResponse, BrowserStatusResponse
from backend.services.resume_service import ResumeService
from backend.services.application_service import already_sent
from backend.services.lifecycle import set_stage

logger = logging.getLogger("agent_kitkat.browser_service")


class BrowserService:
    """
    Coordinates browser automation tasks and updates database models.
    """

    @staticmethod
    async def run_automation(
        db: AsyncSession,
        draft_id: str,
        auto_submit: bool = False,
        headless: Optional[bool] = None,
        confirm_submit: bool = False,
    ) -> BrowserRunResult:
        """
        Execute browser automation for a prepared application draft.

        Safety gates (enforced server-side, whatever the UI sends):
        - auto_submit requires an APPROVED approval request for this draft AND confirm_submit=True.
        - Never runs for an application that was already submitted (no duplicates).
        - Only one run per draft at a time.
        """
        # 1. Fetch Draft
        draft_stmt = select(ApplicationDraft).where(ApplicationDraft.id == draft_id)
        draft_res = await db.execute(draft_stmt)
        draft = draft_res.scalar_one_or_none()

        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application draft with ID '{draft_id}' not found."
            )

        # 2. Fetch Job
        job_stmt = select(Job).where(Job.id == draft.job_id)
        job_res = await db.execute(job_stmt)
        job = job_res.scalar_one_or_none()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Associated job '{draft.job_id}' not found."
            )

        # 2b. Safety gates
        apps_res = await db.execute(select(Application).where(Application.job_id == job.id))
        if any(already_sent(a) for a in apps_res.scalars().all()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An application for this job was already submitted. Agent KitKat will not submit it again."
            )
        if draft.id in browser_agent.get_active_session_ids():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Automation is already running for this draft.")
        if auto_submit:
            appr_res = await db.execute(
                select(ApprovalRequest).where(ApprovalRequest.draft_id == draft.id, ApprovalRequest.status == "approved")
            )
            if appr_res.scalars().first() is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Submission blocked: this application has not been approved by you yet."
                )
            if not confirm_submit:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Submission blocked: explicit confirmation (confirm_submit=true) is required for each application."
                )

        # 3. Fetch Resume File Path
        resume_file_path: Optional[str] = None
        if draft.resume_id:
            res_stmt = select(Resume).where(Resume.id == draft.resume_id)
            res_res = await db.execute(res_stmt)
            resume_obj = res_res.scalar_one_or_none()
            if resume_obj:
                resume_file_path = resume_obj.file_path

        if not resume_file_path:
            active_resume = await ResumeService.get_active_resume(db)
            if active_resume:
                resume_file_path = active_resume.file_path

        # 4. Fetch or Create Application Record
        app_stmt = select(Application).where(Application.draft_id == draft_id)
        app_res = await db.execute(app_stmt)
        app_record = app_res.scalar_one_or_none()

        if not app_record:
            app_record = Application(
                id=str(uuid.uuid4()),
                job_id=job.id,
                draft_id=draft.id,
                status="filling",
                submission_method="browser_automation"
            )
            db.add(app_record)
        else:
            app_record.status = "filling"
            app_record.submission_method = "browser_automation"

        draft.status = "filling"
        await db.commit()

        # 5. Prepare payload for Browser Agent
        job_data = {
            "id": job.id,
            "title": job.title,
            "company_name": job.company or "Unknown Company",
            "application_url": job.url or ""
        }

        draft_data = {
            "cover_letter": draft.cover_letter,
            "form_field_values": draft.form_field_values,
            "custom_answers": draft.custom_answers
        }

        # 6. Execute Browser Automation
        result = await browser_agent.run_application_automation(
            draft_id=draft.id,
            job_data=job_data,
            draft_data=draft_data,
            resume_file_path=resume_file_path,
            auto_submit=auto_submit,
            headless=headless
        )

        # 7. Update Database with Automation Results
        app_record.status = result.status
        app_record.pre_submit_screenshot = result.pre_submit_screenshot
        app_record.post_submit_screenshot = result.post_submit_screenshot
        app_record.browser_logs = result.logs

        if result.status in ("submitted", "submission_unverified"):
            await set_stage(db, app_record, result.status, actor="browser", force=True,
                            note=("Website showed a confirmation message after submission."
                                  if result.status == "submitted" else result.intervention_reason))
            app_record.applied_at = datetime.utcnow()
            app_record.submission_result = (
                "Website showed a confirmation message after submission."
                if result.status == "submitted" else result.intervention_reason
            )
            app_record.failure_reason = None
            draft.status = result.status
        else:
            app_record.submission_result = result.intervention_reason
            app_record.failure_reason = result.intervention_reason
            draft.status = result.status

        draft.pre_submit_screenshot = result.pre_submit_screenshot
        draft.post_submit_screenshot = result.post_submit_screenshot

        await db.commit()
        await db.refresh(app_record)

        return result

    @staticmethod
    async def emergency_stop() -> EmergencyStopResponse:
        """Trigger emergency stop to abort all active browser sessions."""
        stopped = await browser_agent.emergency_stop()
        return EmergencyStopResponse(
            message=f"Emergency stop executed successfully. Terminated {stopped} active browser session(s).",
            stopped_sessions_count=stopped,
            status="emergency_stopped"
        )

    @staticmethod
    def get_status() -> BrowserStatusResponse:
        """Get live status of active browser sessions."""
        active = browser_agent.get_active_session_ids()
        return BrowserStatusResponse(
            is_active=len(active) > 0,
            active_draft_ids=active
        )
