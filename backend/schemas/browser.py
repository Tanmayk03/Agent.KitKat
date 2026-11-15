"""
Agent KitKat - Browser Automation Schemas
Pydantic models for browser automation requests, results, and emergency controls.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class BrowserRunRequest(BaseModel):
    """Request payload to initiate browser automation for a prepared draft."""
    auto_submit: bool = Field(
        default=False,
        description="Whether to submit the application or pause after filling for review."
    )
    headless: Optional[bool] = Field(
        default=None,
        description="Whether to run the browser in headless mode. Defaults to server config."
    )


class BrowserRunResult(BaseModel):
    """Result of a browser automation execution."""
    draft_id: str
    job_id: str
    company_name: str
    job_title: str
    application_url: str
    status: str = Field(
        description="Status: filled_ready_for_review, submitted, paused_captcha, paused_login, paused_unknown_field, halted_emergency, failed"
    )
    requires_human_intervention: bool = False
    intervention_reason: Optional[str] = None
    pre_submit_screenshot: Optional[str] = None
    post_submit_screenshot: Optional[str] = None
    logs: List[str] = Field(default_factory=list)


class EmergencyStopResponse(BaseModel):
    """Response returned upon triggering the browser emergency stop."""
    message: str
    stopped_sessions_count: int
    status: str = "emergency_stopped"


class BrowserStatusResponse(BaseModel):
    """Live status of browser automation worker."""
    is_active: bool
    active_draft_ids: List[str] = Field(default_factory=list)
