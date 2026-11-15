"""
Agent KitKat - Autonomous AI Career Assistant
Main FastAPI Application (Backend Entry Point)
"""

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

    yield

    logger.info("Shutting down %s...", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_FULL_NAME,
    description="Agent KitKat API: Personal autonomous career assistant for job discovery, resume matching, and application automation.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for local development and future dashboard/iPhone access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"  # Local development flexibility
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    logger.info("Mounted production frontend UI at /ui (dist: %s)", frontend_dist_dir)


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
