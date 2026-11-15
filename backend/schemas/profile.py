"""
Agent KitKat - Profile Schemas
Pydantic schemas for personal career profile, education, skills, and preferences.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class EducationDetails(BaseModel):
    degree: str = Field(default="B.Tech", description="Degree name")
    specialization: str = Field(default="Computer Science and Data Science", description="Specialization/Major")
    college: str = Field(default="SRM University, Delhi NCR", description="College/University name")
    cgpa: float = Field(default=8.44, ge=0.0, le=10.0, description="CGPA out of 10")
    graduation: str = Field(default="May 2027", description="Graduation month and year")
    graduation_year: int = Field(default=2027, ge=2020, le=2035, description="Year of graduation")


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
    issuer: str
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
    projects: Optional[List[ProjectItem]] = None
    work_experience: Optional[List[WorkExperienceItem]] = None
    certifications: Optional[List[CertificationItem]] = None
    application_preferences: Optional[ApplicationPreferences] = None
    active_resume_id: Optional[str] = None


class UserProfileResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    location: str
    linkedin_url: str
    github_url: str
    portfolio_url: str
    education: EducationDetails
    preferred_roles: List[str]
    preferred_locations: List[str]
    expected_stipend: str
    work_mode: str
    verified_skills: List[str]
    unverified_skills: List[str]
    projects: List[ProjectItem]
    work_experience: List[WorkExperienceItem]
    certifications: List[CertificationItem]
    application_preferences: ApplicationPreferences
    active_resume_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
