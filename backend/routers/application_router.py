"""
Agent KitKat - Application API Router
Endpoints for application preparation, approval requests, and application tracking.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.application import (
    ApplicationPrepareRequest,
    ApplicationDraftResponse,
    DraftUpdateRequest,
    ApprovalDecisionRequest,
    ApprovalRequestItem,
    ApplicationTrackerItem
)
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
            decision_notes=request.decision_notes
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
