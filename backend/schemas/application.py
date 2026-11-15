"""
Agent KitKat - Application Preparation Schemas
Pydantic schemas for cover letters, answers, form field values, approvals, and application tracker.
"""

from typing import Optional, List, Dict, Any
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
    created_at: datetime


class DraftUpdateRequest(BaseModel):
    cover_letter: Optional[str] = None
    custom_answers: Optional[Dict[str, str]] = None
    form_field_values: Optional[Dict[str, Any]] = None


class ApprovalDecisionRequest(BaseModel):
    action: str = Field(..., description="'approve' or 'reject'")
    decision_notes: Optional[str] = Field(None, description="Optional feedback or notes")


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
    match_score: Optional[float] = None
    submission_method: str
    submission_result: Optional[str] = None
    failure_reason: Optional[str] = None
    applied_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_at: datetime
