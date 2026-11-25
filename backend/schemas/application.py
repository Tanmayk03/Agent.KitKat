"""
Agent KitKat - Application Preparation Schemas
Pydantic schemas for cover letters, answers, form field values, approvals, and application tracker.
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class ApplicationPrepareRequest(BaseModel):
    resume_id: Optional[str] = Field(None, description="Specific resume ID to use (defaults to active resume)")
    policy_override: Optional[str] = Field(None, description="Optional override: 'manual_approval', 'pre_authorized', 'prepare_only'")


class ApplicationDraftResponse(BaseModel):
    id: str
    job_id: str
    company: str
    role: str
    resume_id: Optional[str] = None
    cover_letter: str
    custom_answers: Dict[str, str] = Field(default_factory=dict)
    form_field_values: Dict[str, Any] = Field(default_factory=dict)
    unanswered_questions: List[str] = Field(default_factory=list)
    status: str
    policy_applied: str
    grounding_report: List[Dict[str, Any]] = Field(default_factory=list,
                                                   description="Claims that could not be traced to your profile/resume")
    current_version: int = 1
    created_at: datetime


class DraftUpdateRequest(BaseModel):
    cover_letter: Optional[str] = None
    custom_answers: Optional[Dict[str, str]] = None
    form_field_values: Optional[Dict[str, Any]] = None


class ApprovalDecisionRequest(BaseModel):
    action: Literal["approve", "reject"] = Field(..., description="'approve' or 'reject'")
    decision_notes: Optional[str] = Field(None, description="Optional feedback or notes")
    acknowledge_unverified_claims: bool = Field(
        False, description="Approve even though the grounding check flagged claims (you checked them yourself)")


class ApprovalRequestItem(BaseModel):
    id: str
    job_id: str
    draft_id: str
    company: str
    role: str
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    job_url: Optional[str] = None
    match_score: float
    eligibility_status: str
    policy_applied: str
    status: str
    created_at: datetime
    draft: Optional[ApplicationDraftResponse] = None


class ApplicationTrackerItem(BaseModel):
    id: str
    application_id: Optional[str] = None
    job_id: str
    draft_id: Optional[str] = None
    company: str
    role: str
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    job_url: Optional[str] = None
    status: str
    stage: str = "discovered"
    stage_label: str = "Discovered"
    stage_updated_at: Optional[datetime] = None
    allowed_next_stages: List[str] = Field(default_factory=list)
    approval_status: Optional[str] = None
    eligibility_status: Optional[str] = None
    match_score: Optional[float] = None
    source: Optional[str] = None
    location: Optional[str] = None
    resume_id: Optional[str] = None
    resume_file_name: Optional[str] = None
    confirmation_id: Optional[str] = None
    notes: Optional[str] = None
    follow_up_date: Optional[str] = None
    pre_submit_screenshot: Optional[str] = None
    post_submit_screenshot: Optional[str] = None
    submission_method: str
    submission_result: Optional[str] = None
    failure_reason: Optional[str] = None
    applied_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_at: datetime


class TrackerPage(BaseModel):
    items: List[ApplicationTrackerItem]
    total: int
    page: int
    page_size: int
    stage_counts: Dict[str, int] = Field(default_factory=dict)


class ApplicationUpdateRequest(BaseModel):
    stage: Optional[str] = Field(None, description="New lifecycle stage (validated against allowed transitions)")
    note: Optional[str] = Field(None, max_length=2000, description="Note recorded in the history")
    notes: Optional[str] = Field(None, max_length=10000, description="Free-form notes on the application")
    confirmation_id: Optional[str] = Field(None, max_length=255)
    follow_up_date: Optional[str] = Field(None, pattern=r"^$|^\d{4}-\d{2}-\d{2}$")


class ApplicationEventItem(BaseModel):
    id: str
    from_stage: Optional[str]
    to_stage: Optional[str]
    actor: str
    note: Optional[str]
    created_at: datetime


class DraftVersionItem(BaseModel):
    id: str
    version: int
    source: str
    cover_letter: str
    custom_answers: Dict[str, Any] = Field(default_factory=dict)
    form_field_values: Dict[str, Any] = Field(default_factory=dict)
    grounding_report: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
