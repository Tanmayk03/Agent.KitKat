"""
Agent KitKat - Browser Automation Service

Server-side safety gates (whatever the UI sends):
- Nothing runs while automation is HALTED by Emergency Stop (HTTP 423) until you Resume.
- Nothing runs for an application that was already sent (no duplicates).
- One run per draft at a time.
- Submitting requires an APPROVED approval request for this draft AND confirm_submit=true.
- Preview mode only reads the form: nothing is typed or clicked.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from backend.database.models import Job, Resume, ApplicationDraft, Application, ApprovalRequest
from backend.agents.browser_agent import browser_agent
from backend.schemas.browser import BrowserRunResult, EmergencyStopResponse, BrowserStatusResponse
from backend.services.resume_service import ResumeService
from backend.services.application_service import ApplicationService, already_sent
from backend.services.lifecycle import add_note_event, set_stage
from backend.services.halt import HALT_MESSAGE, is_halted, set_halted

logger = logging.getLogger("agent_kitkat.browser_service")

# Automation outcomes worth a line in the application's history
NOTEWORTHY = {
    "filled_ready_for_review": "Form filled (not submitted); review the screenshot",
    "paused_unknown_field": "Form partly filled; required questions need your answer",
    "paused_captcha": "Stopped at a CAPTCHA / bot check",
    "paused_login": "Stopped at a login page",
    "unsupported_site": "Site not supported for automation; apply manually",
    "failed": "Automation failed",
    "halted_emergency": "Stopped by Emergency Stop",
}


class BrowserService:
    """Coordinates browser automation tasks and updates database models."""

    @staticmethod
    async def _load(db: AsyncSession, draft_id: str) -> Tuple[ApplicationDraft, Job, Optional[str]]:
        draft = (await db.execute(select(ApplicationDraft).where(ApplicationDraft.id == draft_id))).scalar_one_or_none()
        if not draft:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application draft '{draft_id}' not found.")
        job = (await db.execute(select(Job).where(Job.id == draft.job_id))).scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Associated job '{draft.job_id}' not found.")
        resume_path = None
        if draft.resume_id:
            r = (await db.execute(select(Resume).where(Resume.id == draft.resume_id))).scalar_one_or_none()
            resume_path = r.file_path if r else None
        if not resume_path:
            active = await ResumeService.get_active_resume(db)
            resume_path = active.file_path if active else None
        return draft, job, resume_path

    @staticmethod
    async def _common_gates(db: AsyncSession, draft: ApplicationDraft, job: Job) -> Application:
        if await is_halted(db):
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=HALT_MESSAGE)
        apps = (await db.execute(select(Application).where(Application.job_id == job.id))).scalars().all()
        if any(already_sent(a) for a in apps):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="An application for this job was already submitted. Agent KitKat will not submit it again.")
        if draft.id in browser_agent.get_active_session_ids():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Automation is already running for this draft.")
        app = await ApplicationService._app_for_job(db, job.id)
        if app is None:
            app = Application(id=str(uuid.uuid4()), job_id=job.id, draft_id=draft.id, status="draft",
                              stage="discovered", submission_method="manual", created_at=datetime.utcnow())
            db.add(app)
            await db.flush()
        return app

    @staticmethod
    def _payloads(draft: ApplicationDraft, job: Job):
        job_data = {"id": job.id, "title": job.title, "company_name": job.company or "Unknown Company",
                    "application_url": job.url or ""}
        draft_data = {"cover_letter": draft.cover_letter, "form_field_values": draft.form_field_values or {},
                      "custom_answers": draft.custom_answers or {}}
        return job_data, draft_data

    @staticmethod
    def _form_state(result: BrowserRunResult, mode: str) -> dict:
        # Store labels / actions / outcomes, not the values (they live in the draft already)
        return {
            "mode": mode, "adapter": result.adapter, "status": result.status, "at": datetime.utcnow().isoformat(),
            "summary": result.form_summary,
            "fields": [{k: v for k, v in f.items() if k != "value"} for f in result.form_plan],
        }

    @staticmethod
    async def preview(db: AsyncSession, draft_id: str, headless: Optional[bool] = None) -> BrowserRunResult:
        """Open the application page and map its fields. Nothing is typed or clicked."""
        draft, job, resume_path = await BrowserService._load(db, draft_id)
        app = await BrowserService._common_gates(db, draft, job)
        job_data, draft_data = BrowserService._payloads(draft, job)
        result = await browser_agent.run_application_automation(
            draft_id=draft.id, job_data=job_data, draft_data=draft_data, resume_file_path=resume_path,
            auto_submit=False, headless=headless, mode="preview")
        app.form_state = BrowserService._form_state(result, "preview")
        await db.commit()
        return result

    @staticmethod
    async def run_automation(
        db: AsyncSession,
        draft_id: str,
        auto_submit: bool = False,
        headless: Optional[bool] = None,
        confirm_submit: bool = False,
    ) -> BrowserRunResult:
        """Fill the application form (and, only when approved + confirmed, submit it)."""
        draft, job, resume_path = await BrowserService._load(db, draft_id)
        app = await BrowserService._common_gates(db, draft, job)
        if auto_submit:
            approved = (await db.execute(
                select(ApprovalRequest).where(ApprovalRequest.draft_id == draft.id, ApprovalRequest.status == "approved")
            )).scalars().first()
            if approved is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail="Submission blocked: this application has not been approved by you yet.")
            if not confirm_submit:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail="Submission blocked: explicit confirmation (confirm_submit=true) is required for each application.")

        app.draft_id = draft.id
        app.status = "filling"
        app.submission_method = "browser_automation"
        draft.status = "filling"
        await db.commit()

        job_data, draft_data = BrowserService._payloads(draft, job)
        result = await browser_agent.run_application_automation(
            draft_id=draft.id, job_data=job_data, draft_data=draft_data, resume_file_path=resume_path,
            auto_submit=auto_submit, headless=headless, mode="fill")

        app.status = result.status
        app.pre_submit_screenshot = result.pre_submit_screenshot
        app.post_submit_screenshot = result.post_submit_screenshot
        app.browser_logs = result.logs
        app.form_state = BrowserService._form_state(result, "submit" if auto_submit else "fill")
        draft.pre_submit_screenshot = result.pre_submit_screenshot
        draft.post_submit_screenshot = result.post_submit_screenshot

        if result.status in ("submitted", "submission_unverified"):
            evidence = ("Website showed a new confirmation message after submission."
                        if result.status == "submitted" else result.intervention_reason)
            await set_stage(db, app, result.status, actor="browser", force=True, note=evidence)
            app.applied_at = datetime.utcnow()
            app.submission_result = evidence
            app.failure_reason = None
            draft.status = result.status
        else:
            app.submission_result = result.intervention_reason
            app.failure_reason = result.intervention_reason if result.status not in ("filled_ready_for_review",) else None
            # keep the approval-related draft status; the automation outcome lives on the application
            if result.status in NOTEWORTHY:
                await add_note_event(db, app, f"{NOTEWORTHY[result.status]}" +
                                     (f": {result.intervention_reason}" if result.intervention_reason else ""), actor="browser")
        if draft.status == "filling":
            draft.status = "approved" if (await db.execute(select(ApprovalRequest).where(
                ApprovalRequest.draft_id == draft.id, ApprovalRequest.status == "approved"))).scalars().first() else "pending_approval"

        await db.commit()
        return result

    @staticmethod
    async def emergency_stop(db: AsyncSession) -> EmergencyStopResponse:
        """Close every browser, halt all automation and pause the schedule until you Resume."""
        stopped = await browser_agent.emergency_stop()
        await set_halted(db, True)
        from backend.scheduler.daily_scheduler import daily_scheduler
        daily_scheduler.stop()  # pause only; your saved schedule setting is kept for Resume
        logger.warning("Automation HALTED by emergency stop.")
        return EmergencyStopResponse(
            message=f"Emergency stop: closed {stopped} browser session(s). All automation and the daily schedule are halted until you press Resume.",
            stopped_sessions_count=stopped,
            status="emergency_stopped",
        )

    @staticmethod
    async def resume(db: AsyncSession) -> BrowserStatusResponse:
        await set_halted(db, False)
        from backend.scheduler.daily_scheduler import daily_scheduler
        from backend.services.profile_service import ProfileService
        prefs = (await ProfileService.get_or_create_profile(db)).application_preferences or {}
        if prefs.get("scheduler_enabled"):
            daily_scheduler.start_from_prefs(prefs)
        logger.info("Automation resumed.")
        return await BrowserService.get_status(db)

    @staticmethod
    async def get_status(db: AsyncSession) -> BrowserStatusResponse:
        active = browser_agent.get_active_session_ids()
        return BrowserStatusResponse(halted=await is_halted(db), is_active=len(active) > 0, active_draft_ids=active)
