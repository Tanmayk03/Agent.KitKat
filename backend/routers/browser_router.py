"""
Agent KitKat - Browser Automation Router
Endpoints for triggering automated application filling, emergency stopping,
querying live session status, and viewing screenshots.
"""

import os
import logging
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.config import get_settings
from backend.schemas.browser import (
    BrowserRunRequest,
    BrowserRunResult,
    EmergencyStopResponse,
    BrowserStatusResponse
)
from backend.services.browser_service import BrowserService

logger = logging.getLogger("agent_kitkat.browser_router")
settings = get_settings()

router = APIRouter(prefix="/api/browser", tags=["Browser Automation"])


@router.post(
    "/run/{draft_id}",
    response_model=BrowserRunResult,
    status_code=status.HTTP_200_OK,
    summary="Run browser automation for an application draft"
)
async def run_browser_automation(
    draft_id: str,
    payload: BrowserRunRequest = BrowserRunRequest(),
    db: AsyncSession = Depends(get_db)
) -> BrowserRunResult:
    """
    Launch browser automation to fill (and optionally submit) the application.
    - If auto_submit is False, fills form fields and takes pre-submit screenshot for human review.
    - If auto_submit is True, submits the application and verifies confirmation on page.
    - Pauses safely if CAPTCHA, login wall, or unknown required questions are encountered.
    """
    return await BrowserService.run_automation(
        db=db,
        draft_id=draft_id,
        auto_submit=payload.auto_submit,
        headless=payload.headless
    )


@router.post(
    "/emergency-stop",
    response_model=EmergencyStopResponse,
    status_code=status.HTTP_200_OK,
    summary="Emergency Stop: Abort all active browser automations"
)
async def emergency_stop_browser() -> EmergencyStopResponse:
    """
    Kill-switch that immediately halts all active browser automation tasks,
    closes open browser windows, and cleans up resources.
    """
    return await BrowserService.emergency_stop()


@router.get(
    "/status",
    response_model=BrowserStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active browser sessions status"
)
async def get_browser_status() -> BrowserStatusResponse:
    """Returns whether any browser automation sessions are actively running."""
    return BrowserService.get_status()


@router.get(
    "/screenshots/{draft_id}/{filename}",
    summary="Retrieve application form verification screenshot"
)
async def get_screenshot(draft_id: str, filename: str):
    """Retrieve pre-submit or post-submit verification screenshot image."""
    # Prevent directory traversal
    safe_filename = os.path.basename(filename)
    safe_draft_id = os.path.basename(draft_id)

    file_path = os.path.join(settings.SCREENSHOTS_DIR, safe_draft_id, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screenshot '{safe_filename}' not found for draft '{safe_draft_id}'."
        )

    return FileResponse(file_path, media_type="image/png")
