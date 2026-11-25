"""
Agent KitKat - Job Discovery and Scheduler Router
Endpoints for triggering autonomous multi-source job hunting,
managing the daily background scheduler, and querying source statuses.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.schemas.discovery import (
    DiscoveryTriggerRequest,
    DiscoveryRunResult,
    SourceStatusItem,
    SchedulerStatusResponse,
    CareerBoardItem,
    CareerBoardAddRequest,
)
from backend.services.profile_service import ProfileService
from backend.tools.career_boards import parse_board_url
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
async def get_sources(db: AsyncSession = Depends(get_db)) -> List[SourceStatusItem]:
    """All discovery sources: public feeds plus the company career boards you follow."""
    return await DiscoveryService.get_sources_status(db)


@router.get("/health", summary="Per-source health: last run, failures, counts, success rate")
async def get_source_health(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    return await DiscoveryService.source_health(db)


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED, summary="Start a discovery run in the background")
async def start_background_run(payload: DiscoveryTriggerRequest = DiscoveryTriggerRequest()) -> Dict[str, Any]:
    """Returns immediately with a run_id; poll GET /api/discovery/runs/{run_id} for progress."""
    try:
        run_id = await daily_scheduler.start_background_discovery(
            keywords=payload.keywords,
            locations=payload.locations,
            limit_per_source=payload.limit_per_source,
            auto_evaluate=payload.auto_evaluate,
            auto_prepare_applications=payload.auto_prepare_applications,
        )
    except SchedulerBusyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return {"run_id": run_id, "status": "running"}


@router.get("/runs", summary="Recent discovery runs (history)")
async def list_runs(limit: int = Query(default=20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    return await DiscoveryService.list_runs(db, limit)


@router.get("/runs/{run_id}", summary="One discovery run (poll for progress)")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await DiscoveryService.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return run


# ----------------------------------------------------------------- career boards
async def _boards(db: AsyncSession):
    profile = await ProfileService.get_or_create_profile(db)
    return profile, list((profile.application_preferences or {}).get("career_boards") or [])


async def _save_boards(db: AsyncSession, profile, boards) -> None:
    prefs = dict(profile.application_preferences or {})
    prefs["career_boards"] = boards
    profile.application_preferences = prefs
    await db.commit()


@router.get("/boards", response_model=List[CareerBoardItem], summary="Company career boards you follow")
async def list_boards(db: AsyncSession = Depends(get_db)):
    _, boards = await _boards(db)
    return boards


@router.post("/boards", response_model=List[CareerBoardItem], summary="Follow a company career board")
async def add_board(payload: CareerBoardAddRequest, db: AsyncSession = Depends(get_db)):
    try:
        if payload.url:
            ats, token = parse_board_url(payload.url)
        else:
            ats, token = parse_board_url(payload.token or "", payload.ats)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    profile, boards = await _boards(db)
    if any(b.get("ats") == ats and b.get("token") == token for b in boards):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Already following {ats}:{token}.")
    boards.append({"ats": ats, "token": token, "company": (payload.company or token).strip(), "enabled": True})
    await _save_boards(db, profile, boards)
    return boards


@router.delete("/boards/{ats}/{token}", response_model=List[CareerBoardItem], summary="Stop following a board")
async def remove_board(ats: str, token: str, db: AsyncSession = Depends(get_db)):
    profile, boards = await _boards(db)
    remaining = [b for b in boards if not (b.get("ats") == ats and b.get("token") == token)]
    if len(remaining) == len(boards):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
    await _save_boards(db, profile, remaining)
    return remaining


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
