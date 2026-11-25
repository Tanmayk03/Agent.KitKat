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
    summary="Report for one day in your timezone (read-only, computed live)"
)
async def get_daily_report(
    target_date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format (default: today, your timezone)"),
    db: AsyncSession = Depends(get_db)
) -> DailyReportResponse:
    """Activity during that day (from record timestamps) plus a snapshot of the current state. Writes nothing."""
    return await ReportingService.get_daily_report(db, target_date=target_date)


@router.post(
    "/daily/generate",
    response_model=DailyReportResponse,
    summary="Save the report for a day (one row per date; re-saving replaces it)"
)
async def save_daily_report(
    target_date: Optional[str] = Query(default=None, description="YYYY-MM-DD (default: today)"),
    db: AsyncSession = Depends(get_db)
) -> DailyReportResponse:
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
