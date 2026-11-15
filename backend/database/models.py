"""
Agent KitKat - SQLAlchemy Database Models
Phase 2: UserProfile and Resume models.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    JSON,
    ForeignKey
)
from backend.database.db import Base


class UserProfile(Base):
    """
    User Personal Profile & Career Preferences.
    Stores personal, educational, skill, and application preferences.
    """
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # Contact Details
    full_name = Column(String(255), default="")
    email = Column(String(255), default="")
    phone = Column(String(50), default="")
    location = Column(String(255), default="India")
    linkedin_url = Column(String(500), default="")
    github_url = Column(String(500), default="")
    portfolio_url = Column(String(500), default="")

    # Education (stored as structured JSON)
    education = Column(JSON, default=lambda: {
        "degree": "B.Tech",
        "specialization": "Computer Science and Data Science",
        "college": "SRM University, Delhi NCR",
        "cgpa": 8.44,
        "graduation": "May 2027",
        "graduation_year": 2027
    })

    # Preferences
    preferred_roles = Column(JSON, default=lambda: [
        "Software Engineer Intern",
        "Software Developer Intern",
        "Frontend Developer Intern",
        "AI/ML Intern",
        "Data Engineer Intern",
        "Full Stack Developer Intern"
    ])
    preferred_locations = Column(JSON, default=lambda: [
        "India",
        "Remote",
        "Bangalore",
        "Noida",
        "Delhi NCR"
    ])
    expected_stipend = Column(String(100), default="Market Rate / Negotiable")
    work_mode = Column(String(50), default="Any")  # Remote, Hybrid, Onsite, Any

    # Skills tracking: verified via resume vs unverified
    verified_skills = Column(JSON, default=list)
    unverified_skills = Column(JSON, default=lambda: [
        "Python",
        "React",
        "Java",
        "JavaScript",
        "Node.js",
        "Web development"
    ])

    # Portfolio & Experience
    projects = Column(JSON, default=list)
    work_experience = Column(JSON, default=list)
    certifications = Column(JSON, default=list)

    # Application Preferences
    application_preferences = Column(JSON, default=lambda: {
        "daily_search_time": "09:00",
        "max_applications_per_day": 5,
        "min_match_score": 75,
        "submission_policy": "manual_approval",  # manual_approval, pre_authorized, prepare_only
        "search_frequency": "once_daily"
    })

    # Active Resume pointer
    active_resume_id = Column(String(36), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Resume(Base):
    """
    Managed Resumes (PDF / DOCX).
    Stores raw extracted text, parsed structured metadata, and file location.
    """
    __tablename__ = "resumes"

    id = Column(String(36), primary_key=True, index=True)  # UUID4
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(10), nullable=False)  # "pdf" or "docx"
    file_size_bytes = Column(Integer, default=0)

    # Extracted content
    raw_text = Column(Text, default="")
    structured_data = Column(JSON, default=lambda: {
        "extracted_skills": [],
        "education": [],
        "projects": [],
        "experience": [],
        "certifications": []
    })

    # Active status
    is_active = Column(Boolean, default=False)

    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
