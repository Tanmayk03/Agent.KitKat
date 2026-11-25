"""
Agent KitKat - Autonomous AI Career Assistant
Main FastAPI Application (Backend Entry Point)
"""

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.database.db import init_db
from backend.routers.profile_router import router as profile_router
from backend.routers.resume_router import router as resume_router
from backend.routers.job_router import router as job_router
from backend.routers.matching_router import router as matching_router
from backend.routers.application_router import router as application_router
from backend.routers.browser_router import router as browser_router
from backend.routers.discovery_router import router as discovery_router, scheduler_router
from backend.routers.reporting_router import router as reporting_router
from backend.routers.network_router import router as network_router
from backend.schemas.health import HealthCheckResponse
from backend.schemas.ai import AITestRequest, AITestResponse
from backend.services.ollama_service import ollama_service
from backend.security import LOCAL_ORIGIN_REGEX, SAFE_METHODS, is_allowed_origin

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("agent_kitkat.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info("==================================================")
    logger.info("🍫 %s v%s", settings.APP_FULL_NAME, settings.APP_VERSION)
    logger.info("Tagline: %s", settings.APP_TAGLINE)
    logger.info("Environment: %s | Debug: %s", settings.APP_ENV, settings.DEBUG)
    logger.info("Ollama Endpoint: %s", settings.OLLAMA_BASE_URL)
    logger.info("Ollama Target Model: %s", settings.OLLAMA_MODEL)
    logger.info("==================================================")

    # Initial check of Ollama reachability on startup
    health = await ollama_service.check_health()
    if health.status == "connected":
        if health.model_available:
            logger.info("✅ Ollama connected successfully. Model '%s' is ready!", settings.OLLAMA_MODEL)
        else:
            logger.warning(
                "⚠️ Ollama is connected, but model '%s' was not found. Please run `ollama pull %s`.",
                settings.OLLAMA_MODEL,
                settings.OLLAMA_MODEL
            )
    else:
        logger.warning(
            "⚠️ Could not reach Ollama at %s on startup. Please ensure Ollama is running.",
            settings.OLLAMA_BASE_URL
        )

    # Initialize local SQLite database
    logger.info("Initializing database at %s...", settings.DATABASE_URL)
    await init_db()
    logger.info("✅ Database tables initialized successfully.")

    # Restore the persisted autonomous schedule (if the user enabled it)
    from backend.scheduler.daily_scheduler import daily_scheduler
    try:
        await daily_scheduler.restore_from_profile()
    except Exception as e:  # never block startup on the scheduler
        logger.error("Could not restore scheduler state: %s", e)

    yield

    daily_scheduler.shutdown()
    logger.info("Shutting down %s...", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_FULL_NAME,
    description="Agent KitKat API: Personal autonomous career assistant for job discovery, resume matching, and application automation.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS: only this machine, private-LAN devices (your iPhone) and explicitly configured origins.
# Never "*": with credentials that would let any website you visit drive the agent.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_extra_origins,
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from backend.services.halt import AutomationHaltedError  # noqa: E402


@app.exception_handler(AutomationHaltedError)
async def automation_halted_handler(request: Request, exc: AutomationHaltedError):
    return JSONResponse(status_code=423, content={"detail": str(exc)})


@app.middleware("http")
async def reject_cross_site_writes(request: Request, call_next):
    """
    CSRF guard. Browsers always send an Origin header on cross-site POST/PUT/DELETE,
    including "simple" requests that skip CORS preflight. Reject any state-changing
    request whose Origin is not local/LAN/allow-listed.
    """
    if request.method not in SAFE_METHODS:
        origin = request.headers.get("origin")
        if not is_allowed_origin(origin, settings.cors_extra_origins):
            logger.warning("Blocked cross-site %s %s from origin %s", request.method, request.url.path, origin)
            return JSONResponse(status_code=403, content={"detail": "Cross-site request blocked."})
    return await call_next(request)


# Register API Routers
app.include_router(profile_router)
app.include_router(resume_router)
app.include_router(job_router)
app.include_router(matching_router)
app.include_router(application_router)
app.include_router(browser_router)
app.include_router(discovery_router)
app.include_router(scheduler_router)
app.include_router(reporting_router)
app.include_router(network_router)

# Mount Frontend Built UI (React PWA) if available
frontend_dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_dist_dir):
    app.mount("/ui", StaticFiles(directory=frontend_dist_dir, html=True), name="ui")
    assets_dir = os.path.join(frontend_dist_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    logger.info("Mounted production frontend UI at /ui and /assets (dist: %s)", frontend_dist_dir)


@app.get("/manifest.json", include_in_schema=False)
async def get_root_manifest():
    manifest_path = os.path.join(frontend_dist_dir, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    return JSONResponse(status_code=404, content={"detail": "Manifest not found"})


@app.get("/sw.js", include_in_schema=False)
async def get_root_sw():
    sw_path = os.path.join(frontend_dist_dir, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    return JSONResponse(status_code=404, content={"detail": "Service worker not found"})


@app.get("/", tags=["General"])
async def root():
    """Welcome endpoint providing service identity and documentation links."""
    return {
        "app": settings.APP_NAME,
        "full_name": settings.APP_FULL_NAME,
        "tagline": settings.APP_TAGLINE,
        "version": settings.APP_VERSION,
        "status": "online",
        "ui": "/ui",
        "docs": "/docs",
        "health": "/api/health"
    }


@app.get("/api/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check():
    """
    Comprehensive health check:
    - Verifies FastAPI application status
    - Verifies connectivity to the local Ollama instance
    - Verifies that qwen2.5:1.5b is installed and available
    """
    ollama_health = await ollama_service.check_health()

    if ollama_health.status == "connected" and ollama_health.model_available:
        overall_status = "healthy"
    elif ollama_health.status == "connected" and not ollama_health.model_available:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return HealthCheckResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        timestamp=datetime.utcnow(),
        ollama=ollama_health
    )


@app.post("/api/ai/test", response_model=AITestResponse, tags=["AI Runtime"])
async def test_ai_generation(request: AITestRequest):
    """
    Test endpoint for local AI model (Qwen2.5:1.5b).
    Accepts a prompt and returns the model's generated response with latency stats.
    """
    return await ollama_service.generate_response(
        prompt=request.prompt,
        system_prompt=request.system_prompt,
        temperature=request.temperature
    )
