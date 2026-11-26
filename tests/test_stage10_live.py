"""
Live checks: run these on your own computer, where Ollama and the internet are available.

    pytest -m live -v                 (or: .\\test.ps1 -Live)

They use the real local model and the real job sites, but a throwaway database: your data
is never touched. Nothing is submitted anywhere. Optional:
    LIVE_BOARD_URL=https://boards.greenhouse.io/<company>   also check one company career board
    LIVE_ATS_URL=<a real Greenhouse/Lever/Ashby posting>     also preview (read-only) a real form
"""

import os
import time
from urllib.parse import urlparse

import pytest

from backend.services.ollama_service import ollama_service
from backend.tools.job_discovery_sources import DISCOVERY_SOURCES

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


# --------------------------------------------------------------------------- Ollama
async def test_ollama_running_with_model():
    h = await ollama_service.check_health()
    assert h.status == "connected", f"Ollama not reachable at {h.endpoint}: {h.error}. Start it with: ollama serve"
    assert h.model_available, f"Model {h.target_model} missing. Run: ollama pull {h.target_model}"


async def test_ollama_generates_text():
    t = time.time()
    r = await ollama_service.generate_response("Reply with exactly the word: ready", temperature=0)
    assert r.success and "ready" in r.response.lower()
    print(f"Ollama answered in {time.time() - t:.1f}s")


async def test_cover_letter_with_real_model_is_grounded(client):
    """Prepare one draft with the real model; the grounding check must run on its output."""
    h = await ollama_service.check_health()
    assert h.status == "connected" and h.model_available, "needs Ollama with the model (see the first live test)"
    from backend.database.db import AsyncSessionLocal
    from backend.database.models import Job
    import uuid
    jid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(Job(id=jid, company="Acme", title="Python Developer Intern", url=f"https://example.com/{jid}",
                  raw_text="Python, SQL. Batch 2027. Remote India.", required_skills=["Python", "SQL"],
                  source="manual_text", graduation_eligibility=[2027], location="Remote, India", work_mode="Remote"))
        await s.commit()
    d = await client.post(f"/api/applications/prepare/{jid}", json={})
    assert d.status_code == 200, d.text
    draft = d.json()
    assert len(draft["cover_letter"]) > 200
    assert "grounding_report" in draft


# --------------------------------------------------------------------------- job sources
def _check_items(items):
    for it in items:
        assert it.get("title") and it.get("company"), it
        u = urlparse(it.get("url") or "")
        assert u.scheme in ("http", "https") and u.netloc, it.get("url")


@pytest.mark.parametrize("source", [s for s in DISCOVERY_SOURCES if s.is_configured()], ids=lambda s: s.name)
async def test_source_reachable_and_well_formed(source):
    source.reset_run_state()
    items = await source.search(["software", "developer", "intern"], ["India", "Remote"], limit=10)
    _check_items(items)
    print(f"{source.name}: {len(items)} matching listing(s)")


async def test_simplify_feed_is_current():
    import httpx
    from backend.tools.job_discovery_sources import TechInternshipsDiscoverySource
    url = TechInternshipsDiscoverySource.INTERNSHIPS_URL
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
        data = (await c.get(url)).json()
    newest = max((x.get("date_posted") or 0) for x in data)
    age_days = (time.time() - newest) / 86400
    assert age_days < 30, f"Newest listing is {age_days:.0f} days old; set SIMPLIFY_INTERNSHIPS_URL to the current season's feed"


@pytest.mark.skipif(not os.getenv("LIVE_BOARD_URL"), reason="set LIVE_BOARD_URL to check a company career board")
async def test_company_board():
    from backend.tools.career_boards import build_board_sources, parse_board_url
    ats, token = parse_board_url(os.environ["LIVE_BOARD_URL"])
    src = build_board_sources([{"ats": ats, "token": token, "company": token}])[0]
    items = await src.search([], [], limit=50)
    _check_items(items)
    assert src.snapshot_ids is not None, "board did not return its full list"


@pytest.mark.skipif(not os.getenv("LIVE_ATS_URL"), reason="set LIVE_ATS_URL to preview a real application form")
async def test_preview_real_ats_form(client):
    """Read-only: opens the posting, maps the form, types nothing, clicks nothing."""
    from backend.agents.browser_agent import browser_agent
    r = await browser_agent.run_application_automation(
        draft_id="live-preview", job_data={"application_url": os.environ["LIVE_ATS_URL"], "title": "Live", "company_name": "Live"},
        draft_data={"form_field_values": {}, "custom_answers": {}, "cover_letter": ""},
        resume_file_path=None, auto_submit=False, headless=True, mode="preview")
    assert r.status in ("previewed", "paused_captcha", "paused_login", "unsupported_site"), r.status
    print(r.status, r.form_summary, r.intervention_reason)
