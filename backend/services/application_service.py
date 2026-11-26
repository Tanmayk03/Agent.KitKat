"""
Agent KitKat - Application Preparation & Tracking Service

- Prepares grounded drafts (cover letter, screening answers, form fields) and keeps every
  generated / edited / restored version.
- Runs the grounding checker on every draft change; approval is refused while flagged claims
  exist unless you explicitly confirm you checked them.
- Owns the application lifecycle (services/lifecycle.py): shortlist -> draft -> approval ->
  submitted -> confirmed -> assessment / interview -> offer / rejected, with an event history.
- One application per job; anything already sent is never regenerated, edited or resubmitted.
"""

import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, desc, asc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    Job, ApplicationDraft, ApprovalRequest, Application, ApplicationEvent, DraftVersion,
    MatchResult, EligibilityResult, Resume,
)
from backend.schemas.application import (
    ApplicationDraftResponse, DraftUpdateRequest, ApprovalRequestItem, ApplicationTrackerItem,
    ApplicationUpdateRequest, ApplicationEventItem, DraftVersionItem, TrackerPage,
)
from backend.services.profile_service import ProfileService
from backend.services.resume_service import ResumeService
from backend.services.matching_service import MatchingService
from backend.services.lifecycle import (
    SENT_STAGES, STAGES, TRANSITIONS, StageTransitionError, add_note_event, set_stage, stage_label,
)
from backend.agents.application_agent import ApplicationAgent
from backend.agents.grounding import check_draft
from backend.agents.matching_agent import candidate_skill_set

logger = logging.getLogger("agent_kitkat.application_service")

# Legacy automation statuses that mean "already sent" (kept for old rows)
FINAL_APPLICATION_STATES = {"submitted", "submission_unverified", "application_confirmed", "submission_uncertain"}


class ApplicationConflictError(ValueError):
    """Raised when an action would overwrite or duplicate an already-submitted application."""


def already_sent(app: Optional[Application]) -> bool:
    return bool(app) and ((app.stage in SENT_STAGES) or (app.status in FINAL_APPLICATION_STATES))


class ApplicationService:
    """Service managing application preparation, approval workflow, and tracker records."""

    # ------------------------------------------------------------------ helpers
    @staticmethod
    async def _app_for_job(session: AsyncSession, job_id: str) -> Optional[Application]:
        rows = (await session.execute(
            select(Application).where(Application.job_id == job_id).order_by(asc(Application.created_at))
        )).scalars().all()
        return rows[0] if rows else None

    @staticmethod
    async def _grounding(session: AsyncSession, job: Job, cover_letter: str, answers: Dict[str, Any],
                         resume_id: Optional[str]) -> List[Dict[str, Any]]:
        profile = await ProfileService.get_or_create_profile(session)
        resume = await ResumeService.get_resume(session, resume_id) if resume_id else None
        return check_draft(cover_letter, answers, profile=profile,
                           candidate_skills=candidate_skill_set(profile, resume),
                           resume_text=resume.raw_text if resume else "", job=job)

    @staticmethod
    async def _add_version(session: AsyncSession, draft: ApplicationDraft, source: str) -> DraftVersion:
        last = (await session.execute(
            select(func.max(DraftVersion.version)).where(DraftVersion.draft_id == draft.id)
        )).scalar() or 0
        v = DraftVersion(
            id=str(uuid.uuid4()), draft_id=draft.id, version=last + 1, source=source,
            cover_letter=draft.cover_letter, custom_answers=dict(draft.custom_answers or {}),
            form_field_values=dict(draft.form_field_values or {}),
            grounding_report=list(draft.grounding_report or []), created_at=datetime.utcnow(),
        )
        draft.current_version = v.version
        session.add(v)
        return v

    @staticmethod
    def _draft_response(draft: ApplicationDraft, job: Job, policy: str) -> ApplicationDraftResponse:
        return ApplicationDraftResponse(
            id=draft.id, job_id=job.id, company=job.company, role=job.title, resume_id=draft.resume_id,
            cover_letter=draft.cover_letter or "", custom_answers=draft.custom_answers or {},
            form_field_values=draft.form_field_values or {}, unanswered_questions=draft.unanswered_questions or [],
            status=draft.status, policy_applied=policy, grounding_report=draft.grounding_report or [],
            current_version=draft.current_version or 1, created_at=draft.created_at,
        )

    @staticmethod
    async def _ensure_application(session: AsyncSession, job: Job) -> Application:
        app = await ApplicationService._app_for_job(session, job.id)
        if app is None:
            app = Application(id=str(uuid.uuid4()), job_id=job.id, status="draft", stage="discovered",
                              submission_method="manual", created_at=datetime.utcnow())
            session.add(app)
            await session.flush()
        return app

    # ------------------------------------------------------------------ preparation
    @staticmethod
    async def prepare_application(
        session: AsyncSession,
        job_id: str,
        resume_id: Optional[str] = None,
        policy_override: Optional[str] = None
    ) -> ApplicationDraftResponse:
        """Generate (or regenerate) a grounded draft and queue it according to your policy."""
        job = (await session.execute(select(Job).where(Job.id == job_id))).scalars().first()
        if not job:
            raise ValueError(f"Job with ID '{job_id}' not found.")

        app = await ApplicationService._app_for_job(session, job_id)
        if already_sent(app):
            raise ApplicationConflictError(
                f"An application for this job was already sent ({stage_label(app.stage)}). It will not be regenerated."
            )

        profile = await ProfileService.get_or_create_profile(session)
        match_eval = await MatchingService.get_evaluation(session, job_id)
        if not match_eval:
            match_eval = await MatchingService.evaluate_job(session, job_id, resume_id)

        target_resume_id = resume_id or profile.active_resume_id
        resume = await ResumeService.get_resume(session, target_resume_id) if target_resume_id else None

        cover_letter = await ApplicationAgent.generate_cover_letter(job=job, profile=profile, matching_skills=match_eval.matching_skills)
        custom_answers = await ApplicationAgent.prepare_application_answers(job=job, profile=profile, matching_skills=match_eval.matching_skills)
        form_fields = ApplicationAgent.map_form_fields(profile)
        unanswered = ApplicationAgent.identify_unanswered_questions(profile, form_fields, custom_answers)
        grounding = check_draft(cover_letter, custom_answers, profile=profile,
                                candidate_skills=candidate_skill_set(profile, resume),
                                resume_text=resume.raw_text if resume else "", job=job)

        # Every submission needs an explicit per-application approval: "pre_authorized" behaves like manual.
        policy = policy_override or (profile.application_preferences or {}).get("submission_policy", "prepare_only")
        if policy == "prepare_only":
            draft_status, approval_status, stage = "drafted", None, "draft_ready"
        else:
            if policy == "pre_authorized":
                logger.info("Policy 'pre_authorized' is disabled for safety; queuing for manual approval.")
            policy, draft_status, approval_status, stage = "manual_approval", "pending_approval", "pending", "awaiting_approval"

        draft = (await session.execute(select(ApplicationDraft).where(ApplicationDraft.job_id == job.id))).scalars().first()
        if draft is None:
            draft = ApplicationDraft(id=str(uuid.uuid4()), job_id=job.id, created_at=datetime.utcnow())
            session.add(draft)
        draft.resume_id = target_resume_id
        draft.cover_letter = cover_letter
        draft.custom_answers = custom_answers
        draft.form_field_values = form_fields
        draft.unanswered_questions = unanswered
        draft.grounding_report = grounding
        draft.status = draft_status
        await session.flush()
        await ApplicationService._add_version(session, draft, "generated")

        if approval_status:
            appr = (await session.execute(select(ApprovalRequest).where(ApprovalRequest.draft_id == draft.id))).scalars().first()
            if appr:
                appr.status, appr.policy_applied, appr.decided_at, appr.decision_notes = approval_status, policy, None, None
            else:
                session.add(ApprovalRequest(id=str(uuid.uuid4()), job_id=job.id, draft_id=draft.id,
                                            status=approval_status, policy_applied=policy))

        app = await ApplicationService._ensure_application(session, job)
        app.draft_id = draft.id
        app.status = "draft_ready" if draft_status == "drafted" else "awaiting_approval"
        app.resume_id = target_resume_id
        app.resume_file_name = resume.file_name if resume else None
        await set_stage(session, app, stage, note=f"Draft generated (version {draft.current_version})", actor="system", force=True)

        await session.commit()
        await session.refresh(draft)
        return ApplicationService._draft_response(draft, job, policy)

    @staticmethod
    async def get_draft(session: AsyncSession, draft_id: str) -> Optional[ApplicationDraftResponse]:
        row = (await session.execute(
            select(ApplicationDraft, Job).join(Job, ApplicationDraft.job_id == Job.id).where(ApplicationDraft.id == draft_id)
        )).first()
        if not row:
            return None
        draft, job = row
        policy = (await session.execute(
            select(ApprovalRequest.policy_applied).where(ApprovalRequest.draft_id == draft.id)
        )).scalars().first() or "prepare_only"
        return ApplicationService._draft_response(draft, job, policy)

    @staticmethod
    async def _editable_draft(session: AsyncSession, draft_id: str) -> Tuple[ApplicationDraft, Job]:
        row = (await session.execute(
            select(ApplicationDraft, Job).join(Job, ApplicationDraft.job_id == Job.id).where(ApplicationDraft.id == draft_id)
        )).first()
        if not row:
            raise ValueError(f"Draft with ID '{draft_id}' not found.")
        draft, job = row
        app = await ApplicationService._app_for_job(session, job.id)
        if already_sent(app) or draft.status in FINAL_APPLICATION_STATES:
            raise ApplicationConflictError("This application was already sent; its draft can no longer be edited.")
        return draft, job

    @staticmethod
    async def _after_content_change(session: AsyncSession, draft: ApplicationDraft, job: Job, source: str) -> None:
        """Re-check grounding, version it, and send an approved draft back for re-approval."""
        draft.grounding_report = await ApplicationService._grounding(
            session, job, draft.cover_letter, draft.custom_answers or {}, draft.resume_id)
        await ApplicationService._add_version(session, draft, source)
        appr = (await session.execute(select(ApprovalRequest).where(ApprovalRequest.draft_id == draft.id))).scalars().first()
        if appr and appr.status == "approved":
            # The approved text changed: approval no longer covers it.
            appr.status, appr.decided_at = "pending", None
            draft.status = "pending_approval"
            app = await ApplicationService._app_for_job(session, job.id)
            if app and app.stage != "awaiting_approval":
                await set_stage(session, app, "awaiting_approval",
                                note=f"Draft {source} after approval; needs re-approval", actor="system", force=True)

    @staticmethod
    async def update_draft(session: AsyncSession, draft_id: str, update_data: DraftUpdateRequest) -> ApplicationDraftResponse:
        """Edit cover letter / answers / fields. Creates a new version and re-runs the grounding check."""
        draft, job = await ApplicationService._editable_draft(session, draft_id)
        changed = False
        if update_data.cover_letter is not None and update_data.cover_letter != draft.cover_letter:
            draft.cover_letter, changed = update_data.cover_letter, True
        if update_data.custom_answers is not None and update_data.custom_answers != (draft.custom_answers or {}):
            draft.custom_answers, changed = update_data.custom_answers, True
        if update_data.form_field_values is not None and update_data.form_field_values != (draft.form_field_values or {}):
            draft.form_field_values, changed = update_data.form_field_values, True
        if changed:
            await ApplicationService._after_content_change(session, draft, job, "edited")
        await session.commit()
        return await ApplicationService.get_draft(session, draft.id)

    @staticmethod
    async def list_versions(session: AsyncSession, draft_id: str) -> List[DraftVersionItem]:
        rows = (await session.execute(
            select(DraftVersion).where(DraftVersion.draft_id == draft_id).order_by(desc(DraftVersion.version))
        )).scalars().all()
        return [DraftVersionItem(
            id=v.id, version=v.version, source=v.source, cover_letter=v.cover_letter or "",
            custom_answers=v.custom_answers or {}, form_field_values=v.form_field_values or {},
            grounding_report=v.grounding_report or [], created_at=v.created_at,
        ) for v in rows]

    @staticmethod
    async def restore_version(session: AsyncSession, draft_id: str, version: int) -> ApplicationDraftResponse:
        draft, job = await ApplicationService._editable_draft(session, draft_id)
        v = (await session.execute(
            select(DraftVersion).where(DraftVersion.draft_id == draft_id, DraftVersion.version == version)
        )).scalars().first()
        if not v:
            raise ValueError(f"Version {version} not found.")
        draft.cover_letter = v.cover_letter
        draft.custom_answers = dict(v.custom_answers or {})
        draft.form_field_values = dict(v.form_field_values or {})
        await ApplicationService._after_content_change(session, draft, job, "restored")
        await session.commit()
        return await ApplicationService.get_draft(session, draft.id)

    @staticmethod
    async def export_draft(session: AsyncSession, draft_id: str) -> str:
        """A copy-paste-ready prepared application (for sites Agent KitKat must not automate)."""
        row = (await session.execute(
            select(ApplicationDraft, Job).join(Job, ApplicationDraft.job_id == Job.id).where(ApplicationDraft.id == draft_id)
        )).first()
        if not row:
            raise ValueError(f"Draft '{draft_id}' not found.")
        draft, job = row
        from backend.agents.site_adapters import adapter_for
        adapter = adapter_for(job.url or "")
        labels = {"full_name": "Full name", "first_name": "First name", "last_name": "Last name", "email": "Email",
                  "phone": "Phone", "location": "Location", "linkedin_url": "LinkedIn", "github_url": "GitHub",
                  "portfolio_url": "Portfolio", "degree": "Degree", "major": "Major", "university": "University",
                  "cgpa": "CGPA", "graduation_year": "Graduation year"}
        answer_labels = {"why_join": "Why do you want to join?", "relevant_project": "Most relevant project",
                         "availability": "Availability", "salary_expectation": "Stipend / salary expectation"}
        lines = [f"# Application: {job.title} at {job.company}", ""]
        if job.url:
            lines.append(f"Apply here: {job.url}")
        if not adapter.supported:
            lines.append(f"Why this is manual: {adapter.reason}")
        lines += ["", f"Draft version {draft.current_version or 1}", "", "## Form fields", ""]
        for key, label in labels.items():
            val = (draft.form_field_values or {}).get(key)
            lines.append(f"- {label}: {val if val else '(missing in your profile)'}")
        lines += ["", "## Screening answers", ""]
        for key, val in (draft.custom_answers or {}).items():
            shown = "(write your own answer)" if val == "NEEDS_YOUR_INPUT" else val
            lines.append(f"**{answer_labels.get(key, key)}**  \n{shown}\n")
        lines += ["## Cover letter", "", draft.cover_letter or "(none)", ""]
        if draft.grounding_report:
            lines += ["## Check before sending", ""]
            lines += [f"- {i['issue']} (\"{i['sentence'][:120]}\")" for i in draft.grounding_report]
            lines.append("")
        lines += ["## Answer yourself", "",
                  "- Work authorisation, visa sponsorship, demographic and legal/consent questions.",
                  "- After applying, open this job in the Tracker and move it to *Submitted* (add the confirmation ID if you get one)."]
        return "\n".join(lines)

    # ------------------------------------------------------------------ approvals
    @staticmethod
    async def list_approvals(session: AsyncSession) -> List[ApprovalRequestItem]:
        rows = (await session.execute(
            select(ApprovalRequest, Job, ApplicationDraft, MatchResult, EligibilityResult)
            .join(Job, ApprovalRequest.job_id == Job.id)
            .join(ApplicationDraft, ApprovalRequest.draft_id == ApplicationDraft.id)
            .outerjoin(MatchResult, Job.id == MatchResult.job_id)
            .outerjoin(EligibilityResult, Job.id == EligibilityResult.job_id)
            .where(ApprovalRequest.status == "pending")
            .order_by(desc(ApprovalRequest.created_at))
        )).all()
        items, seen = [], set()
        for appr, job, draft, mr, el in rows:
            if appr.id in seen:
                continue
            seen.add(appr.id)
            items.append(ApprovalRequestItem(
                id=appr.id, job_id=job.id, draft_id=draft.id, company=job.company, role=job.title,
                company_name=job.company, job_title=job.title, job_url=job.url,
                match_score=mr.overall_score if mr else 0.0,
                eligibility_status=el.overall_status if el else "UNKNOWN",
                policy_applied=appr.policy_applied, status=appr.status, created_at=appr.created_at,
                draft=ApplicationService._draft_response(draft, job, appr.policy_applied),
            ))
        return items

    @staticmethod
    async def decide_approval(session: AsyncSession, approval_id: str, action: str,
                              decision_notes: Optional[str] = None,
                              acknowledge_unverified_claims: bool = False) -> ApprovalRequestItem:
        appr = (await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))).scalars().first()
        if not appr:
            raise ValueError(f"Approval request '{approval_id}' not found.")
        if appr.status != "pending":
            raise ApplicationConflictError(f"This approval request was already decided ({appr.status}).")
        draft = (await session.execute(select(ApplicationDraft).where(ApplicationDraft.id == appr.draft_id))).scalars().first()
        job = (await session.execute(select(Job).where(Job.id == appr.job_id))).scalars().first()

        if action == "approve":
            issues = (draft.grounding_report or []) if draft else []
            if issues and not acknowledge_unverified_claims:
                raise ApplicationConflictError(
                    f"The draft has {len(issues)} claim(s) that could not be traced to your profile or resume. "
                    "Edit them, or approve with acknowledge_unverified_claims=true after checking each one."
                )
        elif action != "reject":
            raise ValueError(f"Unknown action '{action}'. Use 'approve' or 'reject'.")

        appr.decided_at = datetime.utcnow()
        appr.decision_notes = decision_notes
        app = await ApplicationService._app_for_job(session, appr.job_id) if job else None
        if action == "approve":
            appr.status = "approved"
            if draft:
                draft.status = "approved"
            if app:
                app.status = "approved"
                note = "Approved by you" + (" (flagged claims acknowledged)" if (draft and draft.grounding_report) else "")
                await set_stage(session, app, "draft_ready", note=note + (f": {decision_notes}" if decision_notes else ""), force=True)
        else:
            appr.status = "rejected"
            if draft:
                draft.status = "rejected"
            if app:
                app.status = "withdrawn"
                await set_stage(session, app, "withdrawn", note="Rejected by you" + (f": {decision_notes}" if decision_notes else ""), force=True)

        await session.commit()
        await session.refresh(appr)
        return ApprovalRequestItem(
            id=appr.id, job_id=appr.job_id, draft_id=appr.draft_id,
            company=job.company if job else "Unknown", role=job.title if job else "Unknown",
            match_score=0.0, eligibility_status="UNKNOWN", policy_applied=appr.policy_applied,
            status=appr.status, created_at=appr.created_at,
        )

    # ------------------------------------------------------------------ tracker
    @staticmethod
    async def shortlist(session: AsyncSession, job_id: str, note: Optional[str] = None) -> ApplicationTrackerItem:
        job = (await session.execute(select(Job).where(Job.id == job_id))).scalars().first()
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")
        existing = await ApplicationService._app_for_job(session, job_id)
        if existing:
            raise ApplicationConflictError(f"Already tracked ({stage_label(existing.stage)}).")
        el = (await session.execute(select(EligibilityResult).where(EligibilityResult.job_id == job_id))).scalars().first()
        app = await ApplicationService._ensure_application(session, job)
        await set_stage(session, app, "shortlisted", note=note or "Shortlisted by you")
        if el and el.overall_status in ("PASS", "FAIL"):
            await set_stage(session, app, "eligible" if el.overall_status == "PASS" else "not_eligible",
                            note=f"Eligibility check: {el.overall_status}", actor="system")
        job.status = "shortlisted" if job.status in ("discovered", "analyzed") else job.status
        await session.commit()
        return await ApplicationService.get_tracker_item(session, app.id)

    @staticmethod
    async def update_application(session: AsyncSession, app_id: str, data: ApplicationUpdateRequest) -> ApplicationTrackerItem:
        app = (await session.execute(select(Application).where(Application.id == app_id))).scalars().first()
        if not app:
            raise ValueError(f"Application '{app_id}' not found.")
        if data.stage and data.stage != app.stage:
            if data.stage in ("draft_ready", "awaiting_approval") and not app.draft_id:
                raise StageTransitionError("Prepare a draft first (Opportunities → Prepare application).")
            await set_stage(session, app, data.stage, note=data.note)
        elif data.note:
            await add_note_event(session, app, data.note)
        if data.notes is not None:
            app.notes = data.notes
        if data.confirmation_id is not None:
            app.confirmation_id = data.confirmation_id or None
        if data.follow_up_date is not None:
            app.follow_up_date = data.follow_up_date or None
        app.updated_at = datetime.utcnow()
        await session.commit()
        return await ApplicationService.get_tracker_item(session, app.id)

    @staticmethod
    async def follow_ups(session: AsyncSession, due_by: str) -> List[ApplicationTrackerItem]:
        """Applications with a follow-up date on/before due_by that are still open."""
        rows = (await session.execute(
            ApplicationService._tracker_query()
            .where(Application.follow_up_date.isnot(None), Application.follow_up_date <= due_by,
                   Application.stage.notin_(["rejected", "withdrawn", "offer_received", "not_eligible"]))
            .order_by(asc(Application.follow_up_date))
        )).all()
        return [ApplicationService._to_item(*r) for r in rows]

    @staticmethod
    async def get_events(session: AsyncSession, app_id: str) -> List[ApplicationEventItem]:
        rows = (await session.execute(
            select(ApplicationEvent).where(ApplicationEvent.application_id == app_id).order_by(asc(ApplicationEvent.created_at))
        )).scalars().all()
        return [ApplicationEventItem(id=e.id, from_stage=e.from_stage, to_stage=e.to_stage, actor=e.actor,
                                     note=e.note, created_at=e.created_at) for e in rows]

    @staticmethod
    def _tracker_query():
        return (
            select(Application, Job, MatchResult, EligibilityResult, ApprovalRequest.status)
            .join(Job, Application.job_id == Job.id)
            .outerjoin(MatchResult, Job.id == MatchResult.job_id)
            .outerjoin(EligibilityResult, Job.id == EligibilityResult.job_id)
            .outerjoin(ApprovalRequest, ApprovalRequest.draft_id == Application.draft_id)
        )

    @staticmethod
    def _to_item(app, job, mr, el, approval_status) -> ApplicationTrackerItem:
        return ApplicationTrackerItem(
            id=app.id, application_id=app.id, job_id=job.id, draft_id=app.draft_id,
            company=job.company, role=job.title, company_name=job.company, job_title=job.title, job_url=job.url,
            status=app.status or "", stage=app.stage or "discovered", stage_label=stage_label(app.stage),
            stage_updated_at=app.stage_updated_at, allowed_next_stages=TRANSITIONS.get(app.stage or "discovered", []),
            approval_status=approval_status, eligibility_status=el.overall_status if el else None,
            match_score=mr.overall_score if mr else None, source=job.source, location=job.location,
            resume_id=app.resume_id, resume_file_name=app.resume_file_name, confirmation_id=app.confirmation_id,
            notes=app.notes, follow_up_date=app.follow_up_date,
            pre_submit_screenshot=app.pre_submit_screenshot, post_submit_screenshot=app.post_submit_screenshot,
            form_state=app.form_state, submission_method=app.submission_method or "manual", submission_result=app.submission_result,
            failure_reason=app.failure_reason, applied_at=app.applied_at,
            updated_at=app.updated_at or app.created_at, created_at=app.created_at,
        )

    @staticmethod
    async def get_tracker_item(session: AsyncSession, app_id: str) -> ApplicationTrackerItem:
        row = (await session.execute(ApplicationService._tracker_query().where(Application.id == app_id))).first()
        if not row:
            raise ValueError(f"Application '{app_id}' not found.")
        return ApplicationService._to_item(*row)

    @staticmethod
    async def list_applications(session: AsyncSession) -> List[ApplicationTrackerItem]:
        """Legacy unpaginated list (kept for API compatibility)."""
        page = await ApplicationService.search_applications(session, page_size=1000)
        return page.items

    SORTS = {
        "updated": lambda: desc(func.coalesce(Application.stage_updated_at, Application.created_at)),
        "created": lambda: desc(Application.created_at),
        "applied": lambda: desc(Application.applied_at),
        "company": lambda: asc(Job.company),
        "score": lambda: desc(MatchResult.overall_score),
        "follow_up": lambda: asc(func.coalesce(Application.follow_up_date, "9999-12-31")),
    }

    @staticmethod
    async def search_applications(session: AsyncSession, stage: Optional[str] = None, q: Optional[str] = None,
                                  sort: str = "updated", page: int = 1, page_size: int = 20) -> TrackerPage:
        query = ApplicationService._tracker_query()
        if stage:
            stages = [s for s in stage.split(",") if s in STAGES]
            query = query.where(Application.stage.in_(stages))
        if q:
            like = f"%{q.strip()}%"
            query = query.where(or_(Job.company.ilike(like), Job.title.ilike(like), Application.notes.ilike(like),
                                    Application.confirmation_id.ilike(like)))
        total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
        order = ApplicationService.SORTS.get(sort, ApplicationService.SORTS["updated"])()
        rows = (await session.execute(query.order_by(order).offset((page - 1) * page_size).limit(page_size))).all()
        counts = dict((await session.execute(select(Application.stage, func.count()).group_by(Application.stage))).all())
        return TrackerPage(items=[ApplicationService._to_item(*r) for r in rows], total=total, page=page,
                           page_size=page_size, stage_counts={k: v for k, v in counts.items() if k})


# Singleton instance
application_service = ApplicationService()
