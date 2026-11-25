"""pytest configuration: isolate every test run from your real data (see tests/_isolation.py)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tests._isolation  # noqa: E402,F401  (must run before any backend import)

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from backend.database.db import AsyncSessionLocal, init_db  # noqa: E402
from backend.database import models as m  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services.ollama_service import ollama_service  # noqa: E402


@pytest.fixture(autouse=True)
def no_ollama(monkeypatch):
    """Deterministic tests: the local model is 'offline' unless a test patches it."""
    async def offline(*args, **kwargs):
        raise HTTPException(status_code=503, detail="Ollama disabled in tests")
    monkeypatch.setattr(ollama_service, "generate_response", offline)


@pytest.fixture(autouse=True)
async def clean_db():
    await init_db()
    async with AsyncSessionLocal() as s:
        for model in (m.ApplicationEvent, m.DraftVersion, m.SourceRun, m.DiscoveryRun, m.Application, m.ApprovalRequest, m.ApplicationDraft,
                      m.MatchResult, m.EligibilityResult, m.Job, m.Resume, m.UserProfile, m.DailyReport):
            await s.execute(delete(model))
        await s.commit()
    yield


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
        yield c
