"""
Agent KitKat - Matching & Eligibility API Router
Endpoints for evaluating jobs against profile/resume, viewing match breakdowns,
and ranking opportunities.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.matching import (
    MatchResponse,
    EligibilityResponse,
    JobRankingItem
)
from backend.services.matching_service import matching_service

router = APIRouter(prefix="/api/matching", tags=["Eligibility & Matching Engine"])


@router.post("/evaluate/{job_id}", response_model=MatchResponse)
async def evaluate_job(
    job_id: str,
    resume_id: Optional[str] = Query(None, description="Optional specific resume ID to score against"),
    session: AsyncSession = Depends(get_db)
):
    """
    Evaluate candidate eligibility and calculate transparent weighted match score for a job.
    Weights: Technical Skills (35%), Education & Batch (20%), Projects (20%), Role (15%), Location (10%).
    Hard eligibility failures strictly override the match score.
    """
    try:
        return await matching_service.evaluate_job(
            session=session,
            job_id=job_id,
            resume_id=resume_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/evaluation/{job_id}", response_model=MatchResponse)
async def get_evaluation(
    job_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get stored or computed eligibility and match results for a job."""
    try:
        return await matching_service.get_evaluation(session, job_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/rankings", response_model=List[JobRankingItem])
async def list_job_rankings(
    session: AsyncSession = Depends(get_db)
):
    """List all evaluated opportunities ranked by overall match score descending."""
    return await matching_service.list_rankings(session)
