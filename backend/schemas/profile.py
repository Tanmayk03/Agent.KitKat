"""
Agent KitKat - Profile Schemas
Pydantic schemas for personal career profile, education, skills, and preferences.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class EducationDetails(BaseModel):
    """Your education. Empty values mean 'not provided yet' (eligibility then reports UNKNOWN)."""
    degree: Optional[str] = Field(default=None, description="Degree name, e.g. B.Tech")
    specialization: Optional[str] = Field(default=None, description="Specialization/Major")
    college: Optional[str] = Field(default=None, description="College/University name")
    cgpa: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="CGPA out of 10 (as on your current resume)")
    graduation: Optional[str] = Field(default=None, description="Graduation month and year")
    graduation_year: Optional[int] = Field(default=None, ge=2000, le=2040, description="Year of graduation")
    active_backlogs: Optional[int] = Field(default=None, ge=0, description="Number of active backlogs (None = not provided)")

    @field_validator("cgpa", "graduation_year", "active_backlogs", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return None if v in ("", None) else v


class ProjectItem(BaseModel):
    title: str
    description: str = ""
    tech_stack: List[str] = Field(default_factory=list)
    github_url: Optional[str] = None
    live_url: Optional[str] = None


class WorkExperienceItem(BaseModel):
    company: str
    role: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class CertificationItem(BaseModel):
    name: str
    issuer: str = "Industry"
    issue_date: Optional[str] = None
    credential_url: Optional[str] = None


class ApplicationPreferences(BaseModel):
    daily_search_time: str = Field(default="09:00", description="Time for daily automated search (HH:MM)")
    max_applications_per_day: int = Field(default=5, ge=1, le=50, description="Max applications prepared/submitted per day")
    min_match_score: int = Field(default=75, ge=0, le=100, description="Minimum match percentage required (0-100)")
    submission_policy: str = Field(
        default="manual_approval",
        description="Policy: 'manual_approval', 'pre_authorized', or 'prepare_only'"
    )
    search_frequency: str = Field(default="once_daily", description="Daily search frequency")
    scheduler_enabled: bool = Field(default=False, description="Whether the daily discovery schedule is on")
    availability: Optional[str] = Field(default=None, description="Your availability (used verbatim in screening answers)")
    career_boards: List[Dict[str, Any]] = Field(default_factory=list, description="Company career boards you follow")


class UserProfileUpdate(BaseModel):
    """Fields allowed when updating the profile."""
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    education: Optional[EducationDetails] = None
    preferred_roles: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    expected_stipend: Optional[str] = None
    work_mode: Optional[str] = None  # "Any", "Remote", "Hybrid", "Onsite"
    verified_skills: Optional[List[str]] = None
    unverified_skills: Optional[List[str]] = None
    projects: Optional[List[Union[ProjectItem, Dict[str, Any], str]]] = None
    work_experience: Optional[List[Union[WorkExperienceItem, Dict[str, Any], str]]] = None
    certifications: Optional[List[Union[CertificationItem, Dict[str, Any], str]]] = None
    application_preferences: Optional[ApplicationPreferences] = None
    active_resume_id: Optional[str] = None
    work_authorized_countries: Optional[List[str]] = None


class UserProfileResponse(BaseModel):
    id: int
    full_name: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    location: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    github_url: Optional[str] = ""
    portfolio_url: Optional[str] = ""
    education: EducationDetails
    preferred_roles: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    expected_stipend: Optional[str] = ""
    work_mode: str = "Any"
    verified_skills: List[str] = Field(default_factory=list)
    unverified_skills: List[str] = Field(default_factory=list)
    projects: List[Union[ProjectItem, Dict[str, Any], str]] = Field(default_factory=list)
    work_experience: List[Union[WorkExperienceItem, Dict[str, Any], str]] = Field(default_factory=list)
    certifications: List[Union[CertificationItem, Dict[str, Any], str]] = Field(default_factory=list)
    application_preferences: ApplicationPreferences
    active_resume_id: Optional[str] = None
    work_authorized_countries: Optional[List[str]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
