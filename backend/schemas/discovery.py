"""
Agent KitKat - Discovery and Scheduler Schemas
Pydantic schemas for job discovery triggers, duplicate checking, and scheduling.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DiscoveryTriggerRequest(BaseModel):
    """Payload to trigger an autonomous job discovery sweep."""
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Search keywords/roles. If omitted, uses preferences from user profile."
    )
    locations: Optional[List[str]] = Field(
        default=None,
        description="Target locations. If omitted, uses locations from user profile."
    )
    limit_per_source: int = Field(
        default=5,
        ge=1,
        le=25,
        description="Max opportunities to ingest per source."
    )
    auto_evaluate: bool = Field(
        default=True,
        description="Whether to run eligibility checks and resume matching on newly found jobs."
    )
    auto_prepare_applications: bool = Field(
        default=True,
        description="Whether to draft applications for matching eligible opportunities based on submission policy."
    )


class DiscoveredJobItem(BaseModel):
    """Summarized discovered job opportunity."""
    job_id: str
    title: str
    company: str
    url: Optional[str] = None
    source: str
    eligibility_status: Optional[str] = None
    match_score: Optional[float] = None
    is_duplicate: bool = False


class SourceRunResult(BaseModel):
    """What one source returned during a discovery run."""
    source_name: str
    ok: bool
    fetched: int = 0
    new_saved: int = 0
    duplicates: int = 0
    error: Optional[str] = None
    duration_ms: float = 0.0
    skipped_reason: Optional[str] = None


class DiscoveryRunResult(BaseModel):
    """Result of an autonomous discovery cycle."""
    total_discovered: int
    new_saved: int
    duplicates_skipped: int
    eligible_count: int
    shortlisted_count: int
    prepared_count: int
    failed_sources: int = 0
    item_errors: int = 0
    source_results: List[SourceRunResult] = Field(default_factory=list)
    jobs: List[DiscoveredJobItem] = Field(default_factory=list)


class SourceStatusItem(BaseModel):
    """Health and configuration status of a job discovery source."""
    source_name: str
    is_configured: bool
    description: str


class SchedulerStatusResponse(BaseModel):
    """Live status of the daily autonomous scheduler."""
    is_running: bool
    scheduled_time: str
    next_run_time: Optional[str] = None
    cycle_in_progress: bool = False
    last_run_started_at: Optional[str] = None
    last_run_finished_at: Optional[str] = None
    last_run_status: Optional[str] = None
    last_run_error: Optional[str] = None
