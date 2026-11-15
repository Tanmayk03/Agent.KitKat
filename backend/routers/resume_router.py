"""
Agent KitKat - Resume Management API Router
Endpoints for uploading, listing, viewing, activating, and deleting resumes.
"""

from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.resume import (
    ResumeListItem,
    ResumeDetailResponse,
    ResumeUploadResponse
)
from backend.services.resume_service import resume_service

router = APIRouter(prefix="/api/resumes", tags=["Resume Manager"])


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db)
):
    """
    Upload a resume file (PDF or DOCX).
    Extracts text, segments structured sections, extracts technical skills,
    and cross-verifies against the user profile.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename."
        )

    ext = file.filename.split(".")[-1].lower()
    if ext not in ["pdf", "docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '.{ext}'. Only PDF (.pdf) and Word (.docx) files are supported."
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty."
        )

    try:
        resume, profile, all_skills = await resume_service.save_and_parse_resume(
            session=session,
            file_name=file.filename,
            file_bytes=file_bytes
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}"
        )

    return ResumeUploadResponse(
        message="Resume uploaded, parsed, and verified successfully.",
        resume=ResumeListItem(
            id=resume.id,
            file_name=resume.file_name,
            file_type=resume.file_type,
            file_size_bytes=resume.file_size_bytes,
            is_active=resume.is_active,
            skills_count=len(resume.structured_data.get("extracted_skills", [])),
            uploaded_at=resume.uploaded_at
        ),
        verified_skills=profile.verified_skills or [],
        unverified_skills=profile.unverified_skills or [],
        all_extracted_skills=all_skills
    )


@router.get("", response_model=List[ResumeListItem])
async def list_resumes(session: AsyncSession = Depends(get_db)):
    """List all uploaded resumes with metadata and active status."""
    resumes = await resume_service.list_resumes(session)
    return [
        ResumeListItem(
            id=r.id,
            file_name=r.file_name,
            file_type=r.file_type,
            file_size_bytes=r.file_size_bytes,
            is_active=r.is_active,
            skills_count=len(r.structured_data.get("extracted_skills", [])),
            uploaded_at=r.uploaded_at
        )
        for r in resumes
    ]


@router.get("/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume_detail(
    resume_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Retrieve detailed content, raw text, and parsed structured sections of a resume."""
    resume = await resume_service.get_resume(session, resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume '{resume_id}' not found."
        )
    return resume


@router.put("/{resume_id}/activate", response_model=ResumeDetailResponse)
async def activate_resume(
    resume_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Set a specific resume as active and primary for applications."""
    try:
        resume, _ = await resume_service.set_active_resume(session, resume_id)
        return resume
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Delete a resume and its stored local file."""
    success = await resume_service.delete_resume(session, resume_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume '{resume_id}' not found."
        )
    return {"message": f"Resume '{resume_id}' deleted successfully.", "id": resume_id}
