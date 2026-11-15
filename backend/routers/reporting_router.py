"""
Agent KitKat - Daily Reporting Router
Endpoints for viewing real-data daily career activity reports, summaries, and history.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.reporting import DailyReportResponse
from backend.services.reporting_service import ReportingService

logger = logging.getLogger("agent_kitkat.reporting_router")

router = APIRouter(prefix="/api/reports", tags=["Daily Reports"])


@router.get(
    "/daily",
    response_model=DailyReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get today's daily activity report"
)
async def get_daily_report(
    target_date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format (default: today)"),
    db: AsyncSession = Depends(get_db)
) -> DailyReportResponse:
    """
    Returns today's comprehensive career intelligence report.
    Aggregates real statistics on discovered jobs, eligibility passes/rejections,
    applications prepared, approvals pending, and submission results.
    """
    return await ReportingService.generate_daily_report(db, target_date=target_date)


@router.get(
    "/history",
    response_model=List[DailyReportResponse],
    status_code=status.HTTP_200_OK,
    summary="List past daily activity reports"
)
async def get_report_history(
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> List[DailyReportResponse]:
    """Retrieve historical reports sorted by date descending."""
    return await ReportingService.get_report_history(db, limit=limit)


@router.get(
    "/{report_id}",
    response_model=DailyReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get specific daily report by ID"
)
async def get_report_by_id(
    report_id: str,
    db: AsyncSession = Depends(get_db)
) -> DailyReportResponse:
    """Retrieve details for a specific report."""
    return await ReportingService.get_report_by_id(db, report_id=report_id)
