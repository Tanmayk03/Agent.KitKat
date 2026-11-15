from backend.routers.profile_router import router as profile_router
from backend.routers.resume_router import router as resume_router
from backend.routers.job_router import router as job_router
from backend.routers.matching_router import router as matching_router
from backend.routers.application_router import router as application_router
from backend.routers.browser_router import router as browser_router
from backend.routers.discovery_router import router as discovery_router, scheduler_router
from backend.routers.reporting_router import router as reporting_router
from backend.routers.network_router import router as network_router

__all__ = [
    "profile_router",
    "resume_router",
    "job_router",
    "matching_router",
    "application_router",
    "browser_router",
    "discovery_router",
    "scheduler_router",
    "reporting_router",
    "network_router",
]
