"""
Agent KitKat - Job Discovery and Scheduler Router
Endpoints for triggering autonomous multi-source job hunting,
managing the daily background scheduler, and querying source statuses.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.discovery import (
    DiscoveryTriggerRequest,
    DiscoveryRunResult,
    SourceStatusItem,
    SchedulerStatusResponse
)
from backend.services.discovery_service import DiscoveryService
from backend.scheduler.daily_scheduler import daily_scheduler, SchedulerBusyError

logger = logging.getLogger("agent_kitkat.discovery_router")

router = APIRouter(prefix="/api/discovery", tags=["Job Discovery & Scheduler"])


@router.post(
    "/search",
    response_model=DiscoveryRunResult,
    status_code=status.HTTP_200_OK,
    summary="Trigger autonomous job discovery sweep"
)
async def trigger_discovery_sweep(
    payload: DiscoveryTriggerRequest = DiscoveryTriggerRequest(),
    db: AsyncSession = Depends(get_db)
) -> DiscoveryRunResult:
    """
    Search permitted public sources, filter duplicates, evaluate eligibility,
    score against active resume, and optionally prepare applications for qualifying jobs.
    """
    if daily_scheduler.cycle_in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A discovery cycle is already running.")
    async with daily_scheduler.run_lock:
        return await DiscoveryService.run_discovery(
            db=db,
            keywords=payload.keywords,
            locations=payload.locations,
            limit_per_source=payload.limit_per_source,
            auto_evaluate=payload.auto_evaluate,
            auto_prepare_applications=payload.auto_prepare_applications
        )


@router.get(
    "/sources",
    response_model=List[SourceStatusItem],
    status_code=status.HTTP_200_OK,
    summary="List active job discovery sources"
)
async def get_sources() -> List[SourceStatusItem]:
    """Returns available discovery sources (Remotive, Jobicy, Curated, Adzuna) and configuration status."""
    return DiscoveryService.get_sources_status()


# Scheduler Endpoints
scheduler_router = APIRouter(prefix="/api/scheduler", tags=["Autonomous Scheduler"])


def _scheduler_status() -> SchedulerStatusResponse:
    fmt = lambda d: d.strftime("%Y-%m-%d %H:%M:%S") if d else None
    return SchedulerStatusResponse(
        is_running=daily_scheduler.is_running,
        scheduled_time=daily_scheduler.get_scheduled_time(),
        next_run_time=daily_scheduler.get_next_run_time(),
        cycle_in_progress=daily_scheduler.cycle_in_progress,
        last_run_started_at=fmt(daily_scheduler.last_run_started_at),
        last_run_finished_at=fmt(daily_scheduler.last_run_finished_at),
        last_run_status=daily_scheduler.last_run_status,
        last_run_error=daily_scheduler.last_run_error,
    )


@scheduler_router.post(
    "/start",
    response_model=SchedulerStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Start daily autonomous job hunting schedule"
)
async def start_scheduler(
    hour: int = Query(default=9, ge=0, le=23, description="Hour of the day (0-23) to run discovery"),
    minute: int = Query(default=0, ge=0, le=59, description="Minute of the hour (0-59)")
) -> SchedulerStatusResponse:
    """Starts or reconfigures the daily background scheduler (persisted across restarts)."""
    await daily_scheduler.enable(hour=hour, minute=minute)
    return _scheduler_status()


@scheduler_router.post(
    "/stop",
    response_model=SchedulerStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop/Pause daily autonomous job hunting schedule"
)
async def stop_scheduler() -> SchedulerStatusResponse:
    """Pauses the recurring background schedule (persisted across restarts)."""
    await daily_scheduler.disable()
    return _scheduler_status()


@scheduler_router.post(
    "/trigger",
    status_code=status.HTTP_200_OK,
    summary="Trigger immediate discovery cycle in background"
)
async def trigger_scheduler_now():
    """Immediately runs the complete discovery + reporting cycle (never submits applications)."""
    try:
        return await daily_scheduler.trigger_now()
    except SchedulerBusyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@scheduler_router.get(
    "/status",
    response_model=SchedulerStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get scheduler status and next run time"
)
async def get_scheduler_status() -> SchedulerStatusResponse:
    """Returns whether the scheduler is currently active and the next scheduled execution time."""
    return _scheduler_status()
