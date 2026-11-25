"""
Stage 6 tests: label-based form mapping, sensitive-question protection, site adapters,
preview mode, form state, prepared-application export, global halt.
Playwright tests run against local pages that mimic Greenhouse / Lever / Ashby markup and are
skipped if no Chromium build is installed.
"""

import http.server
import os
import socketserver
import threading
import uuid

import pytest
from sqlalchemy import select

from backend.agents.form_mapper import classify_field
from backend.agents.site_adapters import adapter_for
from backend.config import get_settings
from backend.database.db import AsyncSessionLocal
from backend.database.models import Application, ApplicationDraft, Job, Resume

pytestmark = pytest.mark.asyncio
settings = get_settings()

GREENHOUSE = b"""<html><body><h1>Software Engineer Intern</h1>
<form id="application_form" onsubmit="return false;">
 <div class="field"><label for="first_name">First Name <span>*</span></label><input type="text" id="first_name" name="job_application[first_name]" aria-required="true"></div>
 <div class="field"><label for="last_name">Last Name <span>*</span></label><input type="text" id="last_name" name="job_application[last_name]" aria-required="true"></div>
 <div class="field"><label for="email">Email <span>*</span></label><input type="text" id="email" name="job_application[email]" aria-required="true"></div>
 <div class="field"><label for="phone">Phone</label><input type="text" id="phone" name="job_application[phone]"></div>
 <div class="field"><label for="resume">Resume/CV</label><input type="file" id="resume" name="job_application[resume]" style="display:none"><button type="button">Attach</button></div>
 <div class="field"><label for="q0">LinkedIn Profile</label><input id="q0" name="job_application[answers_attributes][0][text_value]"></div>
 <div class="field"><label for="q1">Why are you interested in working at Acme?</label><textarea id="q1" name="job_application[answers_attributes][1][text_value]" aria-required="true"></textarea></div>
 <div class="field"><label for="q2">Expected graduation year</label><select id="q2" name="job_application[answers_attributes][2][text_value]"><option value="">Select...</option><option>2026</option><option>2027</option><option>2028</option></select></div>
 <div class="field"><label for="q3">Will you now or in the future require sponsorship for employment visa status?</label>
   <select id="q3" name="job_application[answers_attributes][3][boolean_value]" aria-required="true"><option value="">--</option><option>Yes</option><option>No</option></select></div>
 <div id="eeoc_fields">
   <label for="gender">Gender</label><select id="gender" name="job_application[gender]"><option value="">Select</option><option>Male</option><option>Female</option><option>Decline</option></select>
   <label for="race">Race</label><select id="race" name="job_application[race]"><option value="">Select</option><option>Asian</option><option>Decline</option></select>
 </div>
 <input type="submit" value="Submit Application">
</form></body></html>"""

LEVER = b"""<html><body><div class="application-page">
<form action="https://jobs.lever.co/acme/123/apply" class="application-form" onsubmit="return false;">
 <div class="application-question"><div class="application-label">Resume/CV<span class="required">*</span></div>
   <div class="application-field"><input type="file" name="resume" id="resume-upload-input" required></div></div>
 <div class="application-question"><div class="application-label">Full name<span class="required">*</span></div>
   <div class="application-field"><input type="text" name="name" required></div></div>
 <div class="application-question"><div class="application-label">Email<span class="required">*</span></div>
   <div class="application-field"><input type="email" name="email" required></div></div>
 <div class="application-question"><div class="application-label">Current company</div>
   <div class="application-field"><input type="text" name="org"></div></div>
 <div class="application-question"><div class="application-label">LinkedIn URL</div>
   <div class="application-field"><input type="text" name="urls[LinkedIn]"></div></div>
 <div class="application-question"><div class="application-label">GitHub URL</div>
   <div class="application-field"><input type="text" name="urls[GitHub]"></div></div>
 <div class="application-question"><div class="application-label">Additional information</div>
   <div class="application-field"><textarea name="comments" placeholder="Add a cover letter or anything else you want to share."></textarea></div></div>
 <div class="application-question"><div class="application-label">Gender</div>
   <div class="application-field"><select name="eeo[gender]"><option value="">Select</option><option>Male</option><option>Female</option></select></div></div>
 <button type="submit">Submit application</button>
</form></div></body></html>"""

ASHBY = b"""<html><body><div class="ashby-application-form-container"><form onsubmit="return false;">
 <div><label for="_systemfield_name">Name</label><input id="_systemfield_name" name="_systemfield_name" required></div>
 <div><label for="_systemfield_email">Email</label><input id="_systemfield_email" type="email" name="_systemfield_email" required></div>
 <div><label for="_systemfield_resume">Resume</label><input id="_systemfield_resume" type="file" name="_systemfield_resume"></div>
 <div><label for="q_abc123">LinkedIn Profile</label><input id="q_abc123" name="q_abc123"></div>
 <div><label for="q_grad">When do you expect to graduate?</label><input id="q_grad" name="q_grad"></div>
 <fieldset><legend>Are you legally authorized to work in India?</legend>
   <label><input type="radio" name="q_auth" value="Yes" required>Yes</label>
   <label><input type="radio" name="q_auth" value="No">No</label></fieldset>
 <button type="submit">Submit Application</button>
</form></div></body></html>"""

FORM_VALUES = {"full_name": "Test Candidate", "first_name": "Test", "last_name": "Candidate", "email": "t@example.com",
               "phone": "+910000000000", "linkedin_url": "https://linkedin.com/in/test", "github_url": "https://github.com/test",
               "graduation_year": "2027", "degree": "B.Tech", "university": "Example University", "cgpa": "8.44"}
ANSWERS = {"why_join": "I like Acme's developer tools.", "relevant_project": "NEEDS_YOUR_INPUT",
           "availability": "June 2026", "salary_expectation": "As per norms"}


# --------------------------------------------------------------------------- classifier / adapters
@pytest.mark.parametrize("field,expected", [
    ({"type": "text", "label": "First Name *", "name": "job_application[first_name]"}, ("profile", "first_name")),
    ({"type": "text", "label": "Full name", "name": "name"}, ("profile", "full_name")),
    ({"type": "text", "label": "Name", "name": "_systemfield_name"}, ("profile", "full_name")),
    ({"type": "text", "label": "When do you expect to graduate?", "name": "q_9"}, ("profile", "graduation_year")),
    ({"type": "text", "label": "LinkedIn Profile", "name": "q_1"}, ("profile", "linkedin_url")),
    ({"type": "file", "label": "Resume/CV", "name": "resume"}, ("resume", None)),
    ({"type": "file", "label": "Cover Letter", "name": "cover"}, ("cover_letter_file", None)),
    ({"type": "textarea", "label": "Additional information", "placeholder": "Add a cover letter or anything else"}, ("cover_letter", None)),
    ({"type": "textarea", "label": "Why are you interested in working at Acme?"}, ("answer", "why_join")),
    ({"type": "select", "label": "Will you require sponsorship for employment visa status?"}, ("sensitive", None)),
    ({"type": "select", "label": "Gender"}, ("sensitive", None)),
    ({"type": "radio", "label": "Yes", "question": "Are you legally authorized to work in India?"}, ("sensitive", None)),
    ({"type": "checkbox", "label": "I certify that the information is true"}, ("sensitive", None)),
    ({"type": "text", "label": "Date of birth"}, ("sensitive", None)),
    ({"type": "radio", "label": "Yes", "question": "Do you have a driving licence?"}, ("unknown", None)),
    ({"type": "text", "label": "Current company", "name": "org"}, ("unknown", None)),
])
async def test_classify_field(field, expected):
    assert classify_field(field) == expected


@pytest.mark.parametrize("url,name,apply_url,supported", [
    ("https://jobs.lever.co/acme/abc", "lever", "https://jobs.lever.co/acme/abc/apply", True),
    ("https://jobs.lever.co/acme/abc/apply", "lever", "https://jobs.lever.co/acme/abc/apply", True),
    ("https://jobs.ashbyhq.com/acme/uuid", "ashby", "https://jobs.ashbyhq.com/acme/uuid/application", True),
    ("https://boards.greenhouse.io/acme/jobs/123", "greenhouse", "https://boards.greenhouse.io/acme/jobs/123", True),
    ("https://www.linkedin.com/jobs/view/123", "unsupported", None, False),
    ("https://www.naukri.com/job-listings-x", "unsupported", None, False),
    ("https://acme.wd5.myworkdayjobs.com/en-US/careers/job/1", "unsupported", None, False),
    ("https://careers.example.com/apply/1", "generic", "https://careers.example.com/apply/1", True),
])
async def test_adapter_for(url, name, apply_url, supported):
    a = adapter_for(url)
    assert (a.name, a.supported) == (name, supported)
    if apply_url:
        assert a.apply_url == apply_url
    if not supported:
        assert "log" in a.reason.lower()  # login / logged in / logging in


# --------------------------------------------------------------------------- helpers
async def make_draft(url: str, approved: bool = False) -> str:
    rid = str(uuid.uuid4())
    path = os.path.join(settings.RESUMES_DIR, f"{rid}.pdf")
    os.makedirs(settings.RESUMES_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4 test resume")
    async with AsyncSessionLocal() as s:
        job = Job(id=str(uuid.uuid4()), company="Acme", title="Software Engineer Intern", url=url, source="manual_url")
        s.add(job)
        s.add(Resume(id=rid, file_name="cv.pdf", file_path=path, file_type="pdf", raw_text="", structured_data={}, is_active=True))
        d = ApplicationDraft(id=str(uuid.uuid4()), job_id=job.id, resume_id=rid, cover_letter="Dear Acme, ...",
                             form_field_values=FORM_VALUES, custom_answers=ANSWERS, status="approved")
        await s.flush()
        s.add(d)
        s.add(Application(id=str(uuid.uuid4()), job_id=job.id, draft_id=d.id, status="approved", stage="draft_ready"))
        await s.commit()
        return d.id


def _chromium() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return os.path.exists(p.chromium.executable_path)
    except Exception:
        return False


CHROMIUM = _chromium()
needs_browser = pytest.mark.skipif(not CHROMIUM, reason="Playwright Chromium not installed")


class _Handler(http.server.BaseHTTPRequestHandler):
    pages = {"/greenhouse": GREENHOUSE, "/lever": LEVER, "/ashby": ASHBY}

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(self.pages.get(self.path, b"<html><body>nothing here</body></html>"))

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def site():
    srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def by_label(plan):
    return {p["label"].replace("*", "").strip(): p for p in plan}


# --------------------------------------------------------------------------- browser: per ATS
@needs_browser
async def test_greenhouse_form_fill(client, site):
    draft_id = await make_draft(f"{site}/greenhouse")
    r = (await client.post(f"/api/browser/run/{draft_id}", json={"headless": True})).json()
    assert r["adapter"] == "greenhouse"
    plan = by_label(r["form_plan"])
    for label in ("First Name", "Last Name", "Email", "Phone", "LinkedIn Profile", "Why are you interested in working at Acme?"):
        assert plan[label]["result"] == "done", label
    assert plan["Resume/CV"]["action"] == "upload" and plan["Resume/CV"]["result"] == "done"
    assert plan["Expected graduation year"]["action"] == "select" and plan["Expected graduation year"]["value"] == "2027"
    for label in ("Gender", "Race", "Will you now or in the future require sponsorship for employment visa status?"):
        assert plan[label]["action"] == "sensitive" and plan[label]["result"] == "left for you"
    # the required sponsorship question is left for the human -> paused, not submitted
    assert r["status"] == "paused_unknown_field" and "sponsorship" in r["intervention_reason"]


@needs_browser
async def test_lever_form_fill_and_form_state(client, site):
    draft_id = await make_draft(f"{site}/lever")
    r = (await client.post(f"/api/browser/run/{draft_id}", json={"headless": True})).json()
    assert r["adapter"] == "lever" and r["status"] == "filled_ready_for_review"
    plan = by_label(r["form_plan"])
    assert plan["Full name"]["result"] == "done" and plan["Additional information"]["kind"] == "cover_letter"
    assert plan["Current company"]["action"] == "manual" and plan["Gender"]["action"] == "sensitive"
    async with AsyncSessionLocal() as s:
        app = (await s.execute(select(Application).join(ApplicationDraft, ApplicationDraft.job_id == Application.job_id)
                                .where(ApplicationDraft.id == draft_id))).scalars().first()
    assert app.form_state["adapter"] == "lever" and app.form_state["mode"] == "fill"
    assert all("value" not in f for f in app.form_state["fields"])  # values are not duplicated into form state
    assert app.stage == "draft_ready"  # filling never changes the stage to submitted


@needs_browser
async def test_ashby_form_reports_sensitive_required_question(client, site):
    draft_id = await make_draft(f"{site}/ashby")
    r = (await client.post(f"/api/browser/run/{draft_id}", json={"headless": True})).json()
    assert r["adapter"] == "ashby"
    plan = by_label(r["form_plan"])
    assert plan["Name"]["key"] == "full_name" and plan["Name"]["result"] == "done"
    assert plan["When do you expect to graduate?"]["result"] == "done"
    assert r["status"] == "paused_unknown_field" and "authorized to work in India" in r["intervention_reason"]


@needs_browser
async def test_preview_types_nothing(client, site):
    draft_id = await make_draft(f"{site}/greenhouse")
    r = (await client.post(f"/api/browser/preview/{draft_id}", json={"headless": True})).json()
    assert r["status"] == "previewed" and r["form_summary"]["fill"] >= 5
    assert all("result" not in p for p in r["form_plan"])
    assert os.path.exists(r["pre_submit_screenshot"]) and r["pre_submit_screenshot"].endswith("preview.png")
    async with AsyncSessionLocal() as s:
        app = (await s.execute(select(Application).join(ApplicationDraft, ApplicationDraft.job_id == Application.job_id)
                                .where(ApplicationDraft.id == draft_id))).scalars().first()
    assert app.form_state["mode"] == "preview" and app.status == "approved"


# --------------------------------------------------------------------------- unsupported + export
async def test_unsupported_site_is_explained_and_exportable(client):
    draft_id = await make_draft("https://www.linkedin.com/jobs/view/123")
    r = (await client.post(f"/api/browser/run/{draft_id}", json={"headless": True})).json()
    assert r["status"] == "unsupported_site" and "LinkedIn" in r["intervention_reason"]
    md = (await client.get(f"/api/applications/drafts/{draft_id}/export")).text
    assert "Dear Acme" in md and "LinkedIn requires" in md and "(write your own answer)" in md
    assert "t@example.com" in md


# --------------------------------------------------------------------------- global halt
async def test_emergency_stop_halts_everything_until_resume(client):
    from backend.scheduler.daily_scheduler import daily_scheduler
    draft_id = await make_draft("https://careers.example.com/apply/1")
    await client.post("/api/scheduler/start?hour=6&minute=15")
    assert (await client.post("/api/browser/emergency-stop")).status_code == 200
    assert (await client.get("/api/browser/status")).json()["halted"] is True
    assert daily_scheduler.is_running is False

    assert (await client.post(f"/api/browser/run/{draft_id}", json={})).status_code == 423
    assert (await client.post(f"/api/browser/preview/{draft_id}", json={})).status_code == 423
    assert (await client.post("/api/discovery/search", json={})).status_code == 423
    assert (await client.post("/api/discovery/runs", json={})).status_code == 423
    assert (await client.post("/api/scheduler/trigger")).status_code == 423

    r = await client.post("/api/browser/resume")
    assert r.json()["halted"] is False and daily_scheduler.is_running is True
    daily_scheduler.shutdown()
