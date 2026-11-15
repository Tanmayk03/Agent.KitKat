"""
Agent KitKat - Daily Report Schemas
Pydantic schemas for retrieving real-data daily career activity reports.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DailyReportResponse(BaseModel):
    """Complete summary of daily job hunting activity."""
    id: str
    report_date: str  # YYYY-MM-DD
    total_discovered: int
    new_found: int
    eligible_count: int
    rejected_count: int
    unknown_count: int
    shortlisted_count: int
    prepared_count: int
    submitted_count: int
    pending_approvals_count: int
    failed_count: int
    summary_markdown: str
    details_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
