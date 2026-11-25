"""
Agent KitKat - Profile API Router
Endpoints for reading and updating the user profile.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.profile import UserProfileUpdate, UserProfileResponse
from typing import List

from pydantic import BaseModel, Field

from backend.services.profile_service import (
    profile_service, profile_completeness, resume_suggestions, apply_resume_suggestions,
)
from backend.services.resume_service import ResumeService


class ApplySuggestionsRequest(BaseModel):
    resume_id: str
    fields: List[str] = Field(..., min_length=1, description="Suggestion fields you accepted")

router = APIRouter(prefix="/api/profile", tags=["Personal Profile"])


@router.get("", response_model=UserProfileResponse)
async def get_profile(session: AsyncSession = Depends(get_db)):
    """
    Get the current user profile.
    Automatically initializes default profile with SRM B.Tech 2027 details if none exists.
    """
    return await profile_service.get_or_create_profile(session)


@router.put("", response_model=UserProfileResponse)
async def update_profile(
    update_data: UserProfileUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Update editable personal profile fields (contact info, skills, projects, preferences).
    """
    return await profile_service.update_profile(session, update_data)


@router.get("/completeness", summary="Missing or inconsistent profile facts (incl. CGPA vs active resume)")
async def get_completeness(session: AsyncSession = Depends(get_db)):
    profile = await profile_service.get_or_create_profile(session)
    resume = await ResumeService.get_resume(session, profile.active_resume_id) if profile.active_resume_id else None
    return profile_completeness(profile, resume)


@router.get("/resume-suggestions/{resume_id}", summary="Profile values found in a resume, with evidence")
async def get_resume_suggestions(resume_id: str, session: AsyncSession = Depends(get_db)):
    resume = await ResumeService.get_resume(session, resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    profile = await profile_service.get_or_create_profile(session)
    return resume_suggestions(profile, resume)


@router.post("/apply-resume-suggestions", response_model=UserProfileResponse,
             summary="Apply the resume suggestions you selected")
async def post_apply_suggestions(payload: ApplySuggestionsRequest, session: AsyncSession = Depends(get_db)):
    resume = await ResumeService.get_resume(session, payload.resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")
    profile = await profile_service.get_or_create_profile(session)
    return await apply_resume_suggestions(session, profile, resume, payload.fields)
