from backend.routers.profile_router import router as profile_router
from backend.routers.resume_router import router as resume_router
from backend.routers.job_router import router as job_router
from backend.routers.matching_router import router as matching_router
from backend.routers.application_router import router as application_router

__all__ = [
    "profile_router",
    "resume_router",
    "job_router",
    "matching_router",
    "application_router",
]
