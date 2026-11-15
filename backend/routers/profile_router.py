"""
Agent KitKat - Profile API Router
Endpoints for reading and updating the user profile.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.profile import UserProfileUpdate, UserProfileResponse
from backend.services.profile_service import profile_service

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
