from backend.schemas.health import HealthCheckResponse, OllamaHealthStatus
from backend.schemas.ai import AITestRequest, AITestResponse
from backend.schemas.profile import (
    EducationDetails,
    ProjectItem,
    WorkExperienceItem,
    CertificationItem,
    ApplicationPreferences,
    UserProfileUpdate,
    UserProfileResponse,
)
from backend.schemas.resume import (
    ResumeStructuredData,
    ResumeListItem,
    ResumeDetailResponse,
    ResumeUploadResponse,
)
from backend.schemas.job import (
    JobAnalyzeUrlRequest,
    JobAnalyzeTextRequest,
    ExtractedJobDetails,
    JobAnalysisResponse,
    JobListItem,
)

__all__ = [
    "HealthCheckResponse",
    "OllamaHealthStatus",
    "AITestRequest",
    "AITestResponse",
    "EducationDetails",
    "ProjectItem",
    "WorkExperienceItem",
    "CertificationItem",
    "ApplicationPreferences",
    "UserProfileUpdate",
    "UserProfileResponse",
    "ResumeStructuredData",
    "ResumeListItem",
    "ResumeDetailResponse",
    "ResumeUploadResponse",
    "JobAnalyzeUrlRequest",
    "JobAnalyzeTextRequest",
    "ExtractedJobDetails",
    "JobAnalysisResponse",
    "JobListItem",
]
