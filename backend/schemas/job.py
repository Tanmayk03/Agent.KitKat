"""
Agent KitKat - Job Schemas
Pydantic schemas for Manual Job URL analysis, text analysis, and structured extraction.
"""

from typing import Optional, List, Union, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class JobAnalyzeUrlRequest(BaseModel):
    url: str = Field(..., min_length=5, description="Public job listing URL (LinkedIn, Naukri, Career page, etc.)")


class JobAnalyzeTextRequest(BaseModel):
    text: str = Field(..., min_length=20, description="Raw job description text pasted by user")
    title: Optional[str] = Field(None, description="Optional job title if known")
    company: Optional[str] = Field(None, description="Optional company name if known")
    url: Optional[str] = Field(None, description="Optional source URL")


class ExtractedJobDetails(BaseModel):
    company_name: str = Field(default="Unknown Company", description="Hiring company name")
    job_title: str = Field(default="Unknown Role", description="Job/Internship title")
    job_description: str = Field(default="", description="Clean summary of the job description")
    required_qualifications: List[str] = Field(default_factory=list, description="Academic and eligibility requirements")
    required_degree: Optional[str] = Field(None, description="Degree requested (e.g. B.Tech, M.Tech, BCA)")
    graduation_eligibility: List[Union[int, str]] = Field(default_factory=list, description="Eligible graduation batches (e.g. [2026, 2027])")
    minimum_cgpa: Optional[float] = Field(None, description="Minimum cut-off CGPA if stated")
    required_skills: List[str] = Field(default_factory=list, description="Technical and soft skills demanded")
    experience_requirements: Optional[str] = Field(None, description="Experience level (e.g. Fresher, 0-1 years)")
    work_location: str = Field(default="Not Specified", description="Job location")
    work_mode: str = Field(default="Unknown", description="Remote, Hybrid, Onsite, or Unknown")
    salary_or_stipend: Optional[str] = Field(None, description="Salary, hourly rate, or monthly stipend")
    application_deadline: Optional[str] = Field(None, description="Application deadline if mentioned")
    application_url: Optional[str] = Field(None, description="Direct URL to apply")
    job_id: Optional[str] = Field(None, description="Job requisition ID if present")


class JobAnalysisResponse(BaseModel):
    id: str
    source: str
    url: Optional[str]
    extracted: ExtractedJobDetails
    raw_text_length: int
    analysis_duration_ms: float
    requires_manual_paste: bool = False
    message: Optional[str] = None


class JobListItem(BaseModel):
    id: str
    company: str
    title: str
    location: str
    work_mode: str
    source: str
    skills_count: int
    status: str
    url: Optional[str] = None
    salary_stipend: Optional[str] = None
    employment_type: Optional[str] = None
    posted_at: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OpportunityItem(BaseModel):
    """One job with its latest eligibility, match and tracking state."""
    id: str
    title: str
    company: str
    location: str
    work_mode: str
    url: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    salary_stipend: Optional[str] = None
    employment_type: Optional[str] = None
    posted_at: Optional[str] = None
    fetched_at: Optional[datetime] = None
    description: str = ""
    eligibility_status: Optional[str] = None     # PASS | FAIL | UNKNOWN | None (not evaluated yet)
    eligibility_reasons: List[str] = Field(default_factory=list)
    match_score: Optional[float] = None
    above_threshold: bool = False
    recommendation: Optional[str] = None
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    next_action: Optional[str] = None
    application_id: Optional[str] = None
    application_stage: Optional[str] = None
    application_stage_label: Optional[str] = None


class OpportunityPage(BaseModel):
    items: List[OpportunityItem]
    total: int
    page: int
    page_size: int
    pages: int
    facets: Dict[str, int]
    min_match_score: float

