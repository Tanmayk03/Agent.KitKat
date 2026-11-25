"""
Agent KitKat - Job Analysis API Router (Mode B)
Endpoints for analyzing pasted job URLs, raw job description text, and uploaded JD files.
"""

from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.job import (
    OpportunityPage,
    JobAnalyzeUrlRequest,
    JobAnalyzeTextRequest,
    JobAnalysisResponse,
    JobListItem,
    ExtractedJobDetails
)
from backend.services.job_service import job_service
from backend.services import opportunity_service

router = APIRouter(prefix="/api/jobs", tags=["Analyze Job (Mode B)"])


@router.post("/analyze-url", response_model=JobAnalysisResponse)
async def analyze_job_url(
    request: JobAnalyzeUrlRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Mode B: Analyze a publicly accessible job listing by URL.
    Extracts text, uses local Qwen2.5 1.5B to identify requirements,
    and returns structured JSON. If the URL requires authentication or blocks access,
    notifies the user to paste the raw text.
    """
    return await job_service.analyze_from_url(session, request.url)


@router.post("/analyze-text", response_model=JobAnalysisResponse)
async def analyze_job_text(
    request: JobAnalyzeTextRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Mode B: Analyze raw job description text pasted by the user.
    Extracts qualifications, skills, CGPA requirements, batches, and work mode.
    """
    return await job_service.analyze_from_text(
        session=session,
        text=request.text,
        title=request.title,
        company=request.company,
        url=request.url
    )


@router.post("/analyze-file", response_model=JobAnalysisResponse)
async def analyze_job_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db)
):
    """
    Mode B: Upload and analyze a job description PDF or Word document.
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
            detail=f"Unsupported file format '.{ext}'. Only PDF and DOCX files are allowed."
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty."
        )

    try:
        return await job_service.analyze_from_file(
            session=session,
            file_name=file.filename,
            file_bytes=file_bytes
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[JobListItem])
async def list_jobs(session: AsyncSession = Depends(get_db)):
    """List all previously analyzed and discovered jobs."""
    jobs = await job_service.list_jobs(session)
    return [
        JobListItem(
            id=j.id,
            company=j.company,
            title=j.title,
            location=j.location or "Not stated",
            work_mode=j.work_mode,
            source=j.source,
            skills_count=len(j.required_skills or []),
            status=j.status,
            url=j.url,
            salary_stipend=j.salary_stipend,
            employment_type=j.employment_type,
            posted_at=j.posted_at,
            last_seen_at=j.last_seen_at,
            expired_at=j.expired_at,
            created_at=j.created_at
        )
        for j in jobs
    ]


@router.get("/opportunities", response_model=OpportunityPage, summary="Jobs with eligibility, score and tracking state")
async def list_opportunities(
    q: str = Query("", max_length=200),
    eligibility: str = Query("all", pattern="^(all|PASS|UNKNOWN|FAIL|unevaluated)$"),
    remote_only: bool = False,
    include_expired: bool = False,
    tracked: str = Query("all", pattern="^(all|yes|no)$"),
    sort: str = Query("best", pattern="^(best|score|newest|posted)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Default order: eligible first, then needs-checking, then not evaluated, then ineligible; best score first."""
    return await opportunity_service.list_opportunities(
        session, q=q, eligibility=eligibility, remote_only=remote_only, include_expired=include_expired,
        tracked=tracked, sort=sort, page=page, page_size=page_size,
    )


@router.get("/{job_id}")
async def get_job_detail(
    job_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get full details of a specific analyzed job posting."""
    job = await job_service.get_job(session, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found."
        )
    return job
