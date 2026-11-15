"""
Agent KitKat - Resume Schemas
Pydantic schemas for uploaded resumes, extracted data, and verification results.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ResumeStructuredData(BaseModel):
    extracted_skills: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class ResumeListItem(BaseModel):
    id: str
    file_name: str
    file_type: str
    file_size_bytes: int
    is_active: bool
    skills_count: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ResumeDetailResponse(BaseModel):
    id: str
    file_name: str
    file_type: str
    file_size_bytes: int
    raw_text: str
    structured_data: ResumeStructuredData
    is_active: bool
    uploaded_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResumeUploadResponse(BaseModel):
    message: str
    resume: ResumeListItem
    verified_skills: List[str]
    unverified_skills: List[str]
    all_extracted_skills: List[str]
