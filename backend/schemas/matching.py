"""
Agent KitKat - Eligibility & Matching Schemas
Pydantic schemas for deterministic eligibility verification and weighted resume scoring.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class RequirementCheck(BaseModel):
    status: str = Field(..., description="Status: 'PASS', 'FAIL', or 'UNKNOWN'")
    details: str = Field(default="", description="Detailed explanation of the check result")
    label: Optional[str] = Field(None, description="Human name of the check")
    requirement: Optional[str] = Field(None, description="What the posting requires (None = not stated)")
    candidate_value: Optional[str] = Field(None, description="Your value from the profile")
    evidence: Optional[str] = Field(None, description="Quoted posting text / field behind the requirement")
    provenance: Optional[str] = Field(None, description="explicit | inferred | missing")
    hard: bool = Field(True, description="Hard requirement (affects overall eligibility) vs advisory")


class EligibilityResponse(BaseModel):
    job_id: str
    overall_status: str = Field(..., description="'PASS', 'FAIL', or 'UNKNOWN'")
    degree: RequirementCheck
    graduation: RequirementCheck
    cgpa: RequirementCheck
    location: RequirementCheck
    work_mode: RequirementCheck
    experience_level: Optional[RequirementCheck] = None
    # Stage 4: every check (10 dimensions) in display order, keyed by name
    checks: Dict[str, RequirementCheck] = Field(default_factory=dict)
    rejection_reasons: List[str] = Field(default_factory=list)
    unverified_requirements: List[str] = Field(default_factory=list)


class MatchCategoryScores(BaseModel):
    technical_skills: float = Field(..., description="Technical skills score (Weight: 35%)")
    education_and_graduation: float = Field(..., description="Education & batch score (Weight: 20%)")
    projects_and_experience: float = Field(..., description="Projects & experience score (Weight: 20%)")
    role_relevance: float = Field(..., description="Role title relevance score (Weight: 15%)")
    location: float = Field(..., description="Location & work mode score (Weight: 10%)")


class MatchResponse(BaseModel):
    job_id: str
    resume_id: Optional[str] = None
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall weighted match percentage (0-100)")
    category_scores: MatchCategoryScores
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    relevant_projects: List[str] = Field(default_factory=list)
    recommendation: str = Field(..., description="e.g. STRONGLY_RECOMMENDED, RECOMMENDED, CONSIDER, NOT_RECOMMENDED, INELIGIBLE")
    explanation: str = Field(..., description="Transparent breakdown and justification of score")
    factor_explanations: Dict[str, str] = Field(default_factory=dict, description="Why each factor scored what it did")
    na_factors: List[str] = Field(default_factory=list, description="Factors that could not be assessed; weights rescaled")
    next_action: Optional[str] = Field(None, description="Recommended next step")
    eligibility: EligibilityResponse


class JobRankingItem(BaseModel):
    job_id: str
    company: str
    title: str
    location: str
    work_mode: str
    overall_score: float
    eligibility_status: str
    recommendation: str
    matching_skills_count: int
    missing_skills_count: int
    created_at: datetime
