"""
Agent KitKat - SQLAlchemy Database Models
Includes: UserProfile, Resume, Job, EligibilityResult, and MatchResult.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    Float,
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
    location = Column(String(255), default="")
    linkedin_url = Column(String(500), default="")
    github_url = Column(String(500), default="")
    portfolio_url = Column(String(500), default="")

    # Education (stored as structured JSON)
    education = Column(JSON, default=dict)  # filled by you / your resume; never hardcoded

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
    expected_stipend = Column(String(100), default="")
    work_mode = Column(String(50), default="Any")  # Remote, Hybrid, Onsite, Any

    # Skills tracking: verified via resume vs unverified
    verified_skills = Column(JSON, default=list)
    unverified_skills = Column(JSON, default=list)

    # Portfolio & Experience
    projects = Column(JSON, default=list)
    work_experience = Column(JSON, default=list)
    certifications = Column(JSON, default=list)

    # Application Preferences
    application_preferences = Column(JSON, default=lambda: {
        "daily_search_time": "09:00",
        "max_applications_per_day": 5,
        "min_match_score": 75,
        "submission_policy": "manual_approval",  # manual_approval or prepare_only (pre_authorized is treated as manual)
        "search_frequency": "once_daily",
        "scheduler_enabled": False
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


class Job(Base):
    """
    Discovered or manually pasted Job Postings.
    Stores extracted qualifications, skills, eligibility rules, and raw JD.
    """
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, index=True)  # UUID4
    company = Column(String(255), default="Unknown Company", index=True)
    title = Column(String(255), default="Unknown Role", index=True)
    description = Column(Text, default="")
    location = Column(String(255), default="Not Specified")
    work_mode = Column(String(50), default="Unknown")  # Remote, Hybrid, Onsite, Unknown
    url = Column(String(1000), nullable=True, index=True)
    source = Column(String(50), default="manual_url")  # manual_url, manual_text, manual_file, adzuna
    job_id_external = Column(String(255), nullable=True)

    # Requirements extracted by LLM & deterministic rules
    required_degree = Column(String(255), nullable=True)
    graduation_eligibility = Column(JSON, default=list)  # e.g. [2026, 2027]
    minimum_cgpa = Column(Float, nullable=True)
    required_skills = Column(JSON, default=list)
    experience_required = Column(String(255), nullable=True)
    salary_stipend = Column(String(255), nullable=True)
    deadline = Column(String(100), nullable=True)
    employment_type = Column(String(100), nullable=True)
    posted_at = Column(String(40), nullable=True)   # ISO-8601 as published by the source; None if not provided
    fetched_at = Column(DateTime, nullable=True)     # when Agent KitKat ingested it
    last_seen_at = Column(DateTime, nullable=True)   # last discovery run in which the source still listed it
    expired_at = Column(DateTime, nullable=True)     # when the source showed it closed / taken down
    expiry_evidence = Column(String(255), nullable=True)
    dedupe_key = Column(String(600), nullable=True, index=True)  # normalised company|title|location
    url_key = Column(String(1000), nullable=True, index=True)    # normalised URL (tracking params removed)

    # Full text & raw metadata
    raw_text = Column(Text, default="")

    # Workflow Status
    status = Column(String(50), default="analyzed")  # discovered, analyzed, shortlisted, rejected, applied, expired

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EligibilityResult(Base):
    """
    Deterministic Eligibility Verification Result.
    Compares candidate profile against hard job requirements (degree, batch, CGPA, work mode).
    Status values: PASS, FAIL, UNKNOWN.
    """
    __tablename__ = "eligibility_results"

    id = Column(String(36), primary_key=True, index=True)  # UUID4
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    overall_status = Column(String(20), nullable=False)  # PASS, FAIL, UNKNOWN
    degree_status = Column(String(20), default="PASS")
    degree_details = Column(String(500), default="")
    graduation_status = Column(String(20), default="PASS")
    graduation_details = Column(String(500), default="")
    cgpa_status = Column(String(20), default="PASS")
    cgpa_details = Column(String(500), default="")
    location_status = Column(String(20), default="PASS")
    location_details = Column(String(500), default="")
    work_mode_status = Column(String(20), default="PASS")
    work_mode_details = Column(String(500), default="")
    experience_status = Column(String(20), nullable=True)
    experience_details = Column(String(500), nullable=True)

    rejection_reasons = Column(JSON, default=list)
    unverified_requirements = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)


class MatchResult(Base):
    """
    Weighted Resume Matching Result.
    Category Weights:
    - Technical skills: 35%
    - Education and graduation: 20%
    - Projects and experience: 20%
    - Role relevance: 15%
    - Location: 10%
    """
    __tablename__ = "match_results"

    id = Column(String(36), primary_key=True, index=True)  # UUID4
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(String(36), nullable=True)

    overall_score = Column(Float, nullable=False)  # 0.0 - 100.0
    technical_skills_score = Column(Float, default=0.0)  # out of 35
    education_score = Column(Float, default=0.0)         # out of 20
    projects_score = Column(Float, default=0.0)          # out of 20
    role_relevance_score = Column(Float, default=0.0)    # out of 15
    location_score = Column(Float, default=0.0)          # out of 10

    matching_skills = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)
    relevant_projects = Column(JSON, default=list)

    recommendation = Column(String(50), nullable=False)
    explanation = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow)


class ApplicationDraft(Base):
    """
    Prepared Application Draft.
    Stores tailored cover letter, custom answers, mapped profile form fields,
    and any unanswered questions requiring user attention.
    """
    __tablename__ = "application_drafts"

    id = Column(String(36), primary_key=True, index=True)  # UUID4
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(String(36), nullable=True)

    cover_letter = Column(Text, default="")
    custom_answers = Column(JSON, default=dict)
    form_field_values = Column(JSON, default=dict)
    unanswered_questions = Column(JSON, default=list)

    pre_submit_screenshot = Column(String(500), nullable=True)
    post_submit_screenshot = Column(String(500), nullable=True)

    status = Column(String(50), default="drafted")  # drafted, pending_approval, approved, rejected, prepared_only, filling, submitted, paused_captcha, paused_login, paused_unknown_field, halted_emergency

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApprovalRequest(Base):
    """
    Pending Human Approval Request for application submission.
    """
    __tablename__ = "approval_requests"

    id = Column(String(36), primary_key=True, index=True)  # UUID4
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    draft_id = Column(String(36), ForeignKey("application_drafts.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(String(50), default="pending")  # pending, approved, rejected, auto_approved
    policy_applied = Column(String(50), default="manual_approval")  # manual_approval, pre_authorized, prepare_only
    decision_notes = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class Application(Base):
    """
    Tracked Job Application record.
    Maintains complete submission status history.
    """
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, index=True)  # UUID4
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    draft_id = Column(String(36), ForeignKey("application_drafts.id", ondelete="SET NULL"), nullable=True)

    status = Column(String(50), default="draft")  # draft, submitted, submission_failed, skipped, filling, paused_captcha, paused_login, paused_unknown_field, halted_emergency
    submission_method = Column(String(50), default="manual")  # manual, browser_automation, prepare_only
    submission_result = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=True)
    pre_submit_screenshot = Column(String(500), nullable=True)
    post_submit_screenshot = Column(String(500), nullable=True)
    browser_logs = Column(JSON, default=list)
    applied_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyReport(Base):
    """
    Persisted Daily Activity and Career Intelligence Report.
    Records discovered jobs, eligibility breakdowns, application statuses,
    and formatted executive summaries based purely on real database data.
    """
    __tablename__ = "daily_reports"

    id = Column(String(36), primary_key=True, index=True)  # UUID4
    report_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD

    total_discovered = Column(Integer, default=0)
    new_found = Column(Integer, default=0)
    eligible_count = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    unknown_count = Column(Integer, default=0)
    shortlisted_count = Column(Integer, default=0)
    prepared_count = Column(Integer, default=0)
    submitted_count = Column(Integer, default=0)
    pending_approvals_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)

    summary_markdown = Column(Text, default="")
    details_json = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)




class DiscoveryRun(Base):
    """One discovery cycle (manual, scheduled or background)."""
    __tablename__ = "discovery_runs"

    id = Column(String(36), primary_key=True, index=True)
    trigger = Column(String(20), default="manual")      # manual, scheduled, background
    status = Column(String(20), default="running")      # running, success, partial, failed
    progress = Column(String(255), default="")
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    total_fetched = Column(Integer, default=0)
    new_saved = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    expired_marked = Column(Integer, default=0)
    failed_sources = Column(Integer, default=0)
    eligible_count = Column(Integer, default=0)
    shortlisted_count = Column(Integer, default=0)
    prepared_count = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    result_json = Column(JSON, nullable=True)


class SourceRun(Base):
    """What one source did during one discovery run (source-health history)."""
    __tablename__ = "source_runs"

    id = Column(String(36), primary_key=True, index=True)
    run_id = Column(String(36), ForeignKey("discovery_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_name = Column(String(120), nullable=False, index=True)
    ok = Column(Boolean, default=False)
    skipped_reason = Column(String(255), nullable=True)
    fetched = Column(Integer, default=0)
    new_saved = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    expired_marked = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    http_status = Column(Integer, nullable=True)
    duration_ms = Column(Float, default=0.0)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)


# Registers SQLAlchemy listeners that keep Job.dedupe_key / Job.url_key up to date.
import backend.tools.duplicate_checker  # noqa: E402,F401
