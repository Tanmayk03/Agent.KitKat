"""
Agent KitKat - Application API Router
Endpoints for application preparation, approval requests, and application tracking.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.application import (
    ApplicationPrepareRequest,
    ApplicationDraftResponse,
    DraftUpdateRequest,
    ApprovalDecisionRequest,
    ApprovalRequestItem,
    ApplicationTrackerItem,
    ApplicationUpdateRequest,
    ApplicationEventItem,
    DraftVersionItem,
    TrackerPage,
)
from backend.services.lifecycle import STAGES, TRANSITIONS, StageTransitionError
from backend.services.application_service import application_service, ApplicationConflictError

router = APIRouter(prefix="/api/applications", tags=["Application Preparation & Tracker"])


@router.post("/prepare/{job_id}", response_model=ApplicationDraftResponse)
async def prepare_application(
    job_id: str,
    request: Optional[ApplicationPrepareRequest] = None,
    session: AsyncSession = Depends(get_db)
):
    """
    Step 7 & Step 9: Prepare tailored cover letter, custom answers,
    and form field mappings from verified profile information.
    Applies submission policy (Manual Approval, Pre-authorized, Prepare Only).
    """
    resume_id = request.resume_id if request else None
    policy_override = request.policy_override if request else None

    try:
        return await application_service.prepare_application(
            session=session,
            job_id=job_id,
            resume_id=resume_id,
            policy_override=policy_override
        )
    except ApplicationConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/drafts/{draft_id}", response_model=ApplicationDraftResponse)
async def get_draft(
    draft_id: str,
    session: AsyncSession = Depends(get_db)
):
    """View prepared application draft."""
    draft = await application_service.get_draft(session, draft_id)
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft '{draft_id}' not found."
        )
    return draft


@router.put("/drafts/{draft_id}", response_model=ApplicationDraftResponse)
async def update_draft(
    draft_id: str,
    update_data: DraftUpdateRequest,
    session: AsyncSession = Depends(get_db)
):
    """Edit drafted cover letter, custom answers, or mapped fields."""
    try:
        return await application_service.update_draft(session, draft_id, update_data)
    except ApplicationConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/approvals", response_model=List[ApprovalRequestItem])
async def list_pending_approvals(
    session: AsyncSession = Depends(get_db)
):
    """List all application drafts awaiting human review and approval."""
    return await application_service.list_approvals(session)


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalRequestItem)
async def decide_approval(
    approval_id: str,
    request: ApprovalDecisionRequest,
    session: AsyncSession = Depends(get_db)
):
    """Approve or reject a pending application submission."""
    try:
        return await application_service.decide_approval(
            session=session,
            approval_id=approval_id,
            action=request.action,
            decision_notes=request.decision_notes,
            acknowledge_unverified_claims=request.acknowledge_unverified_claims,
        )
    except ApplicationConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/tracker", response_model=List[ApplicationTrackerItem])
async def list_applications_tracker(
    session: AsyncSession = Depends(get_db)
):
    """Step 10: View all tracked applications and their current status."""
    return await application_service.list_applications(session)


def _conflict(e: Exception):
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/drafts/{draft_id}/versions", response_model=List[DraftVersionItem], summary="All versions of a draft")
async def list_draft_versions(draft_id: str, session: AsyncSession = Depends(get_db)):
    return await application_service.list_versions(session, draft_id)


@router.post("/drafts/{draft_id}/versions/{version}/restore", response_model=ApplicationDraftResponse,
             summary="Restore an earlier version (creates a new version)")
async def restore_draft_version(draft_id: str, version: int, session: AsyncSession = Depends(get_db)):
    try:
        return await application_service.restore_version(session, draft_id, version)
    except ApplicationConflictError as e:
        raise _conflict(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/drafts/{draft_id}/export", response_class=PlainTextResponse,
            summary="Prepared application as Markdown (for sites that must be applied to manually)")
async def export_draft(draft_id: str, session: AsyncSession = Depends(get_db)):
    try:
        return PlainTextResponse(await application_service.export_draft(session, draft_id), media_type="text/markdown")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/stages", summary="Lifecycle stages and allowed transitions")
async def list_stages():
    return {"stages": STAGES, "transitions": TRANSITIONS}


@router.get("", response_model=TrackerPage, summary="Tracked applications (filter, search, sort, paginate)")
async def search_applications(
    stage: Optional[str] = Query(None, description="Comma-separated stages"),
    q: Optional[str] = Query(None, max_length=200, description="Search company, title, notes, confirmation ID"),
    sort: str = Query("updated", pattern="^(updated|created|applied|company|score|follow_up)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    return await application_service.search_applications(session, stage=stage, q=q, sort=sort, page=page, page_size=page_size)


@router.post("/shortlist/{job_id}", response_model=ApplicationTrackerItem, summary="Start tracking a job")
async def shortlist_job(job_id: str, session: AsyncSession = Depends(get_db)):
    try:
        return await application_service.shortlist(session, job_id)
    except ApplicationConflictError as e:
        raise _conflict(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{app_id}", response_model=ApplicationTrackerItem, summary="Change stage / notes / confirmation / follow-up")
async def update_application(app_id: str, payload: ApplicationUpdateRequest, session: AsyncSession = Depends(get_db)):
    try:
        return await application_service.update_application(session, app_id, payload)
    except StageTransitionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{app_id}/events", response_model=List[ApplicationEventItem], summary="History of an application")
async def application_events(app_id: str, session: AsyncSession = Depends(get_db)):
    return await application_service.get_events(session, app_id)
