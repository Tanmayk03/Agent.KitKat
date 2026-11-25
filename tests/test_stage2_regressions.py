"""
Stage 2 regression tests (pytest). Each test pins down a bug found in AUDIT_REPORT.md.

Run:  python -m pytest -q tests/test_stage2_regressions.py
All external services (Ollama, job APIs) are mocked; Playwright tests are skipped
automatically if no Chromium build is installed.
"""

import asyncio
import http.server
import os
import socketserver
import threading
import uuid

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from backend.config import get_settings
from backend.database.db import AsyncSessionLocal, init_db
from backend.database.models import (
    Application, ApplicationDraft, ApprovalRequest, EligibilityResult, Job, MatchResult, Resume, UserProfile,
)
from backend.main import app
from backend.services.ollama_service import ollama_service

settings = get_settings()
pytestmark = pytest.mark.asyncio


# Shared fixtures (no_ollama, clean_db, client) live in tests/conftest.py


async def make_job(**kw) -> str:
    defaults = dict(id=str(uuid.uuid4()), company="Acme", title="Software Engineer Intern",
                    url=f"https://example.com/jobs/{uuid.uuid4()}", location="Bangalore, India",
                    work_mode="Onsite", raw_text="Software Engineer Intern at Acme", source="manual_text")
    defaults.update(kw)
    async with AsyncSessionLocal() as s:
        s.add(Job(**defaults))
        await s.commit()
    return defaults["id"]


async def make_draft(job_id: str, approval: str = None, app_status: str = None) -> str:
    async with AsyncSessionLocal() as s:
        d = ApplicationDraft(id=str(uuid.uuid4()), job_id=job_id, cover_letter="Hello",
                             form_field_values={"first_name": "Test", "email": "t@example.com"},
                             status="pending_approval")
        s.add(d)
        await s.flush()
        if approval:
            s.add(ApprovalRequest(id=str(uuid.uuid4()), job_id=job_id, draft_id=d.id, status=approval))
        if app_status:
            s.add(Application(id=str(uuid.uuid4()), job_id=job_id, draft_id=d.id, status=app_status))
        await s.commit()
        return d.id


# --------------------------------------------------------------------------- C4 isolation
async def test_tests_use_a_throwaway_database():
    assert "kitkat_test_" in settings.DATABASE_URL
    assert "storage/agent_kitkat.db" not in settings.DATABASE_URL.replace("\\", "/")


# --------------------------------------------------------------------------- C5 CORS / CSRF
async def test_cors_does_not_reflect_foreign_origins(client):
    r = await client.get("/api/profile", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


async def test_cross_site_write_is_blocked(client):
    r = await client.post("/api/browser/emergency-stop", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


async def test_lan_and_local_origins_are_allowed(client):
    for origin in ("http://localhost:5173", "http://192.168.1.23:5173", "http://10.0.0.5:5173"):
        r = await client.post("/api/browser/emergency-stop", headers={"Origin": origin})
        assert r.status_code == 200, origin
        assert r.headers.get("access-control-allow-origin") == origin


# --------------------------------------------------------------------------- C1 approval gate
async def test_unapproved_draft_cannot_be_submitted(client):
    draft_id = await make_draft(await make_job(), approval="pending")
    r = await client.post(f"/api/browser/run/{draft_id}", json={"auto_submit": True, "confirm_submit": True})
    assert r.status_code == 409
    assert "not been approved" in r.json()["detail"]


async def test_approved_draft_still_needs_explicit_confirmation(client):
    draft_id = await make_draft(await make_job(), approval="approved")
    r = await client.post(f"/api/browser/run/{draft_id}", json={"auto_submit": True})
    assert r.status_code == 409
    assert "confirm_submit" in r.json()["detail"]


async def test_already_submitted_application_is_never_rerun(client):
    draft_id = await make_draft(await make_job(), approval="approved", app_status="submitted")
    r = await client.post(f"/api/browser/run/{draft_id}", json={"auto_submit": False})
    assert r.status_code == 409


# --------------------------------------------------------------------------- C2/C3 browser behaviour
FORM_PAGE = b"""<html><body><h2>Apply</h2><p>Thanks for your interest in Acme!</p>
<form id="f" onsubmit="return false;">
<input name="first_name"><input type="email" name="email">
<p>Do you have a disability?</p>
<input type="radio" name="disability" id="dis_yes" value="yes"> Yes
<input type="radio" name="disability" value="no"> No
<p>Are you authorized to work?</p>
<input type="radio" name="work_authorization" value="yes"> Yes
<input type="radio" name="work_authorization" value="no"> No
<textarea id="other" name="anything_else"></textarea>
<button type="submit">Submit</button></form></body></html>"""

REAL_SUBMIT_PAGE = b"""<html><body><h2>Apply</h2>
<form onsubmit="document.body.innerHTML='<h1>Application submitted</h1>'; return false;">
<input name="first_name"><input type="email" name="email"><button type="submit">Submit</button>
</form></body></html>"""


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return os.path.exists(p.chromium.executable_path)
    except Exception:
        return False


CHROMIUM = _chromium_available()


class _Handler(http.server.BaseHTTPRequestHandler):
    pages = {}

    def do_GET(self):
        body = self.pages.get(self.path, b"not found")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def form_server():
    _Handler.pages = {"/form": FORM_PAGE, "/real": REAL_SUBMIT_PAGE}
    srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.mark.skipif(not CHROMIUM, reason="Playwright Chromium not installed")
async def test_browser_never_answers_sensitive_radios_or_misplaces_cover_letter(form_server):
    from backend.agents.browser_agent import browser_agent
    from playwright.async_api import async_playwright

    # Inspect the filled page directly by re-running the fill helper on a live page
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{form_server}/form")
        from backend.agents.form_mapper import EXTRACT_FIELDS_JS, plan_fields
        plan = plan_fields(await page.evaluate(EXTRACT_FIELDS_JS),
                           {"form_field_values": {"first_name": "T"}, "cover_letter": "My letter", "custom_answers": {}}, False)
        await browser_agent._apply_plan(page, plan, None, lambda m: None)
        assert not await page.locator("#dis_yes").is_checked()
        assert await page.locator("input[name='work_authorization']:checked").count() == 0
        assert await page.locator("#other").input_value() == ""
        await browser.close()


@pytest.mark.skipif(not CHROMIUM, reason="Playwright Chromium not installed")
async def test_preexisting_thank_you_text_is_not_a_confirmation(client, form_server):
    draft_id = await make_draft(await make_job(url=f"{form_server}/form"), approval="approved")
    r = await client.post(f"/api/browser/run/{draft_id}",
                          json={"auto_submit": True, "confirm_submit": True, "headless": True})
    assert r.status_code == 200
    assert r.json()["status"] == "submission_unverified"


@pytest.mark.skipif(not CHROMIUM, reason="Playwright Chromium not installed")
async def test_new_confirmation_message_counts_as_submitted(client, form_server):
    draft_id = await make_draft(await make_job(url=f"{form_server}/real"), approval="approved")
    r = await client.post(f"/api/browser/run/{draft_id}",
                          json={"auto_submit": True, "confirm_submit": True, "headless": True})
    assert r.json()["status"] == "submitted"


# --------------------------------------------------------------------------- C6 dedupe
async def test_duplicate_checker_survives_shared_external_ids():
    from backend.tools.duplicate_checker import DuplicateChecker
    await make_job(job_id_external="0", source="src_a", company="A", title="x")
    await make_job(job_id_external="0", source="src_b", company="B", title="y")
    async with AsyncSessionLocal() as s:
        dup, _ = await DuplicateChecker.check_duplicate(s, external_id="0", source="src_a")
        assert dup
        dup, _ = await DuplicateChecker.check_duplicate(s, external_id="0", source="src_c")
        assert not dup


async def test_url_normalisation_keeps_identifying_query_params():
    from backend.tools.duplicate_checker import DuplicateChecker as D
    assert D.normalize_url("https://x.com/job?id=1") != D.normalize_url("https://x.com/job?id=2")
    assert D.normalize_url("https://x.com/job/?id=1&utm_source=li") == D.normalize_url("https://X.com/job?id=1")


async def test_discovery_reports_failed_sources_and_isolates_items(monkeypatch):
    from backend.services import discovery_service as ds
    from backend.tools.job_discovery_sources import BaseDiscoverySource, SourceFetchError

    class Broken(BaseDiscoverySource):
        name = "broken"

        async def search(self, *a, **k):
            raise SourceFetchError("HTTP 503")

    class Good(BaseDiscoverySource):
        name = "good"

        async def search(self, *a, **k):
            item = dict(title="Software Engineer Intern", company="Acme", url="https://acme.example/1",
                        location="Bangalore, India", work_mode="Onsite", source="good", job_id_external="7",
                        raw_text="Software Engineer Intern at Acme")
            return [item, dict(item)]  # same listing twice in one batch

    monkeypatch.setattr(ds, "DISCOVERY_SOURCES", [Broken(), Good()])
    async with AsyncSessionLocal() as s:
        res = await ds.DiscoveryService.run_discovery(s, auto_evaluate=True, auto_prepare_applications=False)
    by_name = {r.source_name: r for r in res.source_results}
    assert by_name["broken"].ok is False and "503" in by_name["broken"].error
    assert by_name["good"].fetched == 2 and by_name["good"].new_saved == 1 and by_name["good"].duplicates == 1
    assert res.failed_sources == 1


# --------------------------------------------------------------------------- H4 no fabricated fields
async def test_connectors_do_not_invent_fields():
    from backend.tools.job_discovery_sources import (
        ArbeitnowDiscoverySource, JobicyDiscoverySource, RemotiveDiscoverySource, TechInternshipsDiscoverySource,
    )
    arb = ArbeitnowDiscoverySource().parse([
        {"title": "Software Engineer Intern", "company_name": "Acme", "url": "https://a/1", "remote": True,
         "location": "Berlin", "description": "<p>intern</p>", "slug": "acme-1", "created_at": 1732500000},
        {"title": "Software Engineer Intern", "company_name": "", "url": "https://a/2", "remote": True,
         "location": "", "description": "", "slug": "x"},
    ], 10)
    assert len(arb) == 1 and arb[0]["salary_stipend"] is None and arb[0]["posted_at"].startswith("2024-11")

    rem = RemotiveDiscoverySource().parse([
        {"id": 5, "title": "Junior Python Developer", "company_name": "R", "url": "https://r/5",
         "description": "entry level", "candidate_required_location": "Worldwide", "salary": ""},
    ], 10)
    assert rem[0]["salary_stipend"] is None

    job = JobicyDiscoverySource().parse([
        {"id": 9, "jobTitle": "Junior Data Engineer", "companyName": "J", "url": "https://j/9",
         "jobDescription": "", "jobGeo": "India", "annualSalaryMin": 600000, "annualSalaryMax": 900000,
         "salaryCurrency": "INR"},
    ], 10)
    assert job[0]["salary_stipend"] == "INR 600000-900000 per year"

    simp = TechInternshipsDiscoverySource().parse([
        {"id": "abc", "title": "Software Engineer Intern", "company_name": "S", "url": "https://s/1",
         "locations": ["Bengaluru, India"], "active": True},
    ], True)
    assert simp[0]["work_mode"] == "Unknown" and simp[0]["salary_stipend"] is None


# --------------------------------------------------------------------------- H5/H6 extraction
async def test_word_be_is_not_a_degree_and_body_seniority_ignored():
    from backend.agents.job_reader import JobReaderAgent
    f = JobReaderAgent.extract_deterministic_features(
        "You will be working with senior engineers on the rest of our platform.", title="Software Engineer Intern")
    assert f["required_degree"] is None
    assert f["experience_required"].startswith("Intern")
    assert "REST API" not in f["required_skills"]


async def test_llm_example_values_are_not_accepted(monkeypatch):
    from backend.agents.job_reader import JobReaderAgent
    from backend.schemas.ai import AITestResponse

    async def copycat(*a, **k):
        return AITestResponse(success=True, model="m", prompt="p", duration_ms=1, response=(
            '{"company_name": "Acme", "minimum_cgpa": 7.5, "graduation_eligibility": [2026, 2027],'
            ' "salary_or_stipend": "₹25,000/month", "work_location": "Bangalore", "required_skills": ["Python", "Kafka"]}'))
    monkeypatch.setattr(ollama_service, "generate_response", copycat)
    text = "Acme is hiring a Python intern. Join our friendly team in Pune."
    details, _ = await JobReaderAgent.analyze_job_text(text)
    assert details.minimum_cgpa is None
    assert details.graduation_eligibility == []
    assert details.salary_or_stipend is None
    assert details.work_location == "Not stated"
    assert "Kafka" not in details.required_skills and "Python" in details.required_skills
    assert details.company_name == "Acme"


async def test_skill_regex_false_positives():
    from backend.tools.resume_parser import ResumeParser
    assert ResumeParser.extract_skills("Curriculum Vitae (CV)\nSection C\nI will go ahead and express interest") == []
    found = ResumeParser.extract_skills("Languages: Python, C, Java\nBuilt REST APIs with Node.js and Express.js")
    assert {"C", "Python", "Java", "REST API", "Node.js", "Express.js"} <= set(found)


# --------------------------------------------------------------------------- H3 eligibility
async def _evaluate(job_kwargs):
    from backend.services.matching_service import MatchingService
    job_id = await make_job(**job_kwargs)
    async with AsyncSessionLocal() as s:
        return await MatchingService.evaluate_job(s, job_id)


async def test_missing_batch_is_unknown_not_pass():
    res = await _evaluate(dict(graduation_eligibility=[], title="Software Engineer Intern"))
    assert res.eligibility.graduation.status == "UNKNOWN"
    assert res.eligibility.overall_status == "UNKNOWN"


async def test_hard_failure_overrides_score():
    res = await _evaluate(dict(graduation_eligibility=[2024, 2025], required_skills=["Python"]))
    assert res.eligibility.overall_status == "FAIL"
    assert res.recommendation == "INELIGIBLE"


async def test_missing_profile_cgpa_is_unknown(client):
    await client.get("/api/profile")
    async with AsyncSessionLocal() as s:
        p = (await s.execute(select(UserProfile))).scalars().first()
        p.education = {**p.education, "cgpa": None}
        await s.commit()
    res = await _evaluate(dict(minimum_cgpa=7.0, graduation_eligibility=[2027]))
    assert res.eligibility.cgpa.status == "UNKNOWN"


async def test_mca_label_is_not_treated_as_chartered_accountancy():
    res = await _evaluate(dict(required_degree="Master's / M.Tech / MCA", graduation_eligibility=[2027]))
    assert res.eligibility.degree.status == "UNKNOWN"


async def test_experience_check_is_persisted(client):
    job_id = await make_job(graduation_eligibility=[2027])
    await client.post(f"/api/matching/evaluate/{job_id}")
    r = await client.get(f"/api/matching/evaluation/{job_id}")
    assert r.json()["eligibility"]["experience_level"]["status"] == "PASS"


# --------------------------------------------------------------------------- H1/H2 contracts
async def test_frontend_api_client_sends_backend_field_names():
    src = open(os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "services", "api.js"), encoding="utf-8").read()
    assert "JSON.stringify({ text, title, company })" in src
    assert "action, decision_notes" in src
    assert "raw_text" not in src


async def test_approval_decision_contract(client):
    job_id = await make_job()
    async with AsyncSessionLocal() as s:
        d = ApplicationDraft(id=str(uuid.uuid4()), job_id=job_id, status="pending_approval")
        s.add(d)
        await s.flush()
        a = ApprovalRequest(id=str(uuid.uuid4()), job_id=job_id, draft_id=d.id, status="pending")
        s.add(a)
        await s.commit()
        appr_id = a.id
    assert (await client.post(f"/api/applications/approvals/{appr_id}/decide",
                              json={"decision": "approved", "notes": ""})).status_code == 422
    r = await client.post(f"/api/applications/approvals/{appr_id}/decide", json={"action": "approve"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    r = await client.post(f"/api/applications/approvals/{appr_id}/decide", json={"action": "reject"})
    assert r.status_code == 409  # already decided


async def test_analyze_text_contract(client):
    r = await client.post("/api/jobs/analyze-text", json={"text": "Backend Developer Intern. Python, FastAPI. Remote."})
    assert r.status_code == 200
    assert r.json()["extracted"]["work_mode"] == "Remote"


# --------------------------------------------------------------------------- H7/H8 applications
async def test_answers_are_grounded_and_sensitive_fields_not_prefilled(client):
    job_id = await make_job(graduation_eligibility=[2027])
    r = await client.post(f"/api/applications/prepare/{job_id}", json={})
    assert r.status_code == 200
    d = r.json()
    assert d["custom_answers"]["relevant_project"] == "NEEDS_YOUR_INPUT"  # test profile has no projects
    assert d["custom_answers"]["availability"] == "NEEDS_YOUR_INPUT"
    assert "work_authorization" not in d["form_field_values"]
    assert "requires_sponsorship" not in d["form_field_values"]
    assert "robust projects" not in d["cover_letter"]
    assert d["status"] == "pending_approval"


async def test_pre_authorized_policy_never_auto_approves(client):
    job_id = await make_job(graduation_eligibility=[2027])
    r = await client.post(f"/api/applications/prepare/{job_id}", json={"policy_override": "pre_authorized"})
    assert r.json()["status"] == "pending_approval"


async def test_submitted_application_is_not_regenerated(client):
    job_id = await make_job()
    await make_draft(job_id, approval="approved", app_status="submitted")
    r = await client.post(f"/api/applications/prepare/{job_id}", json={})
    assert r.status_code == 409


# --------------------------------------------------------------------------- M1/M2 uploads & SSRF
async def test_upload_filename_cannot_escape_resume_folder(client):
    from tests.test_phase2 import create_test_pdf_bytes
    pdf = create_test_pdf_bytes()
    r = await client.post("/api/resumes/upload",
                          files={"file": ("..\\..\\..\\evil.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as s:
        stored = (await s.execute(select(Resume))).scalars().first()
    root = os.path.abspath(settings.RESUMES_DIR)
    assert os.path.commonpath([os.path.abspath(stored.file_path), root]) == root
    assert ".." not in stored.file_name


async def test_oversized_upload_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)
    r = await client.post("/api/resumes/upload", files={"file": ("cv.pdf", b"%PDF-1.4 x", "application/pdf")})
    assert r.status_code == 400


async def test_url_analysis_refuses_local_targets(client):
    r = await client.post("/api/jobs/analyze-url", json={"url": "http://127.0.0.1:11434/api/tags"})
    body = r.json()
    assert body["requires_manual_paste"] is True
    assert "local network" in body["message"]


# --------------------------------------------------------------------------- H9 scheduler
async def test_scheduler_state_persists_and_runs_never_overlap(client):
    from backend.scheduler.daily_scheduler import daily_scheduler
    r = await client.post("/api/scheduler/start?hour=7&minute=30")
    assert r.json()["is_running"] is True
    async with AsyncSessionLocal() as s:
        prefs = (await s.execute(select(UserProfile))).scalars().first().application_preferences
    assert prefs["scheduler_enabled"] is True and prefs["daily_search_time"] == "07:30"

    async with daily_scheduler.run_lock:
        assert (await client.post("/api/scheduler/trigger")).status_code == 409
        assert (await client.post("/api/discovery/search", json={})).status_code == 409

    r = await client.post("/api/scheduler/stop")
    assert r.json()["is_running"] is False
    daily_scheduler.shutdown()


# --------------------------------------------------------------------------- C7 personal data
async def test_new_profile_without_seed_is_empty(monkeypatch, tmp_path):
    from backend.services import profile_service as ps
    monkeypatch.setattr(ps.settings, "PROFILE_SEED_FILE", str(tmp_path / "missing.json"))
    async with AsyncSessionLocal() as s:
        p = await ps.ProfileService.get_or_create_profile(s)
    assert p.full_name == "" and p.email == "" and p.phone == ""
    assert p.education == {}


async def test_no_personal_contact_details_in_tracked_source():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    needles = ("7905170353", "tanmaykapoor003")
    for folder in ("backend", "frontend/src", "scripts"):
        for dirpath, _, files in os.walk(os.path.join(root, folder)):
            for name in files:
                if name.endswith((".py", ".js", ".jsx", ".json")):
                    text = open(os.path.join(dirpath, name), encoding="utf-8", errors="ignore").read()
                    assert not any(n in text for n in needles), os.path.join(dirpath, name)


# --------------------------------------------------------------------------- country-restricted remote
async def test_country_restricted_remote_is_not_open_to_india():
    from backend.tools.job_discovery_sources import classify_location
    assert classify_location("Remote in USA")[0] == "restricted_remote"
    assert classify_location("London, UK, Remote in India")[0] == "india"
    assert classify_location("Worldwide", "Remote")[0] == "open_remote"
    assert classify_location("Berlin", "Remote")[0] == "remote_region_unclear"
    assert classify_location("Zurich")[0] == "foreign"


async def test_eligibility_fails_remote_in_usa_and_flags_unclear_region():
    res = await _evaluate(dict(location="Remote in USA", work_mode="Remote", graduation_eligibility=[2027]))
    assert res.eligibility.location.status == "FAIL"
    res = await _evaluate(dict(location="Berlin", work_mode="Remote", graduation_eligibility=[2027]))
    assert res.eligibility.location.status == "UNKNOWN"


async def test_rankings_put_ineligible_jobs_last(client):
    good = await make_job(company="Good", graduation_eligibility=[2027], required_skills=["Python"])
    bad = await make_job(company="Bad", graduation_eligibility=[2024], required_skills=["Python"])
    for j in (good, bad):
        await client.post(f"/api/matching/evaluate/{j}")
    ranks = (await client.get("/api/matching/rankings")).json()
    assert ranks[-1]["company"] == "Bad" and ranks[-1]["eligibility_status"] == "FAIL"


async def test_explicit_location_line_is_extracted():
    from backend.agents.job_reader import JobReaderAgent
    f = JobReaderAgent.extract_deterministic_features("Role: Intern\nLocation: Bangalore (Remote friendly)\nPython")
    assert f["location"] == "Bangalore (Remote friendly)"
