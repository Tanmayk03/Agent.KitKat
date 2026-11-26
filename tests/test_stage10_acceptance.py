"""
Acceptance: one complete journey through the real API, a real resume file and a real browser.

resume upload → paste a job (Mode B) → evaluate → prepare → safety gates → approve →
fill (nothing sent) → submit only with explicit confirmation → tracker, report, backup.
Ollama is offline (conftest), so everything here must work without the AI.
"""

import http.server
import io
import os
import socketserver
import threading
import zipfile

import pytest

from backend.maintenance import backup

pytestmark = pytest.mark.asyncio

FORM = b"""<html><body><h1>Backend Engineer Intern - Acme Robotics</h1>
<form id="apply" onsubmit="document.body.innerHTML='<h2>Thank you for applying to Acme Robotics!</h2>'; return false;">
 <label for="fn">First Name *</label><input id="fn" name="first_name" required>
 <label for="ln">Last Name *</label><input id="ln" name="last_name" required>
 <label for="em">Email *</label><input id="em" type="email" name="email" required>
 <label for="cv">Resume *</label><input id="cv" type="file" name="resume" required>
 <label for="g">Gender</label><select id="g" name="gender"><option value="">Select</option><option>Female</option><option>Male</option><option>Decline to self-identify</option></select>
 <button type="submit">Submit Application</button>
</form></body></html>"""

JOB_TEXT = """Acme Robotics is hiring a Backend Engineer Intern (2027 batch).
Location: Remote (India). Eligibility: B.Tech / B.E. in Computer Science or related, graduating in 2027.
Skills: Python, FastAPI, SQL, React. You will build REST APIs and internal dashboards.
Stipend: INR 40,000 per month. Duration: 6 months."""


class _H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(FORM)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def ats():
    srv = socketserver.TCPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/acme/backend-intern/apply"
    srv.shutdown()


def resume_pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in ["Test Candidate", "test.candidate@example.com", "EDUCATION",
                 "B.Tech Computer Science and Data Science, Example University, 2023-2027, CGPA 8.44",
                 "SKILLS", "Python, FastAPI, SQL, React, JavaScript, Git",
                 "PROJECTS", "Campus Events API - FastAPI and SQLite REST service with a React dashboard"]:
        c.drawString(60, y, line)
        y -= 22
    c.save()
    return buf.getvalue()


def chromium_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return os.path.exists(p.chromium.executable_path)
    except Exception:
        return False


@pytest.mark.skipif(not chromium_ok(), reason="Playwright Chromium not installed")
async def test_full_journey(client, ats):
    # 1. resume: parsed from the file, skills verified only if literally present
    r = await client.post("/api/resumes/upload", files={"file": ("cv.pdf", resume_pdf(), "application/pdf")})
    assert r.status_code == 200, r.text
    resume = r.json()
    rid = resume.get("id") or resume.get("resume_id") or resume["resume"]["id"]
    assert (await client.put(f"/api/resumes/{rid}/activate")).status_code == 200

    # 2. Mode B: paste a posting
    r = await client.post("/api/jobs/analyze-text", json={"text": JOB_TEXT, "title": "Backend Engineer Intern",
                                                           "company": "Acme Robotics", "url": ats})
    assert r.status_code == 200, r.text
    job_id = r.json().get("job_id") or r.json()["id"]

    # 3. evaluate: deterministic eligibility + explainable score
    ev = (await client.post(f"/api/matching/evaluate/{job_id}")).json()
    assert ev["eligibility"]["overall_status"] in ("PASS", "UNKNOWN")
    assert 0 <= ev["overall_score"] <= 100 and ev["next_action"]
    opp = (await client.get("/api/jobs/opportunities", params={"q": "Acme Robotics"})).json()["items"][0]
    assert opp["id"] == job_id and opp["match_score"] == round(ev["overall_score"], 1)

    # 4. prepare: creates a draft + pending approval; never submits
    d = await client.post(f"/api/applications/prepare/{job_id}", json={})
    assert d.status_code == 200, d.text
    draft = d.json()
    again = (await client.post(f"/api/applications/prepare/{job_id}", json={})).json()
    assert again["id"] == draft["id"]               # re-preparing makes a new version of the same draft, not a duplicate
    apps = [i for i in (await client.get("/api/applications", params={"page_size": 100})).json()["items"] if i["job_id"] == job_id]
    assert len(apps) == 1
    approval = next(a for a in (await client.get("/api/applications/approvals")).json() if a["draft_id"] == draft["id"])

    # 5. gates: no submission before approval, even with confirmation
    r = await client.post(f"/api/browser/run/{draft['id']}", json={"auto_submit": True, "confirm_submit": True, "headless": True})
    assert r.status_code == 409 and "not been approved" in r.json()["detail"]

    # 6. approve (you checked any flagged claims yourself)
    r = await client.post(f"/api/applications/approvals/{approval['id']}/decide",
                          json={"action": "approve", "acknowledge_unverified_claims": True})
    assert r.status_code == 200, r.text

    # 7. approved but not confirmed: still refused
    r = await client.post(f"/api/browser/run/{draft['id']}", json={"auto_submit": True, "headless": True})
    assert r.status_code == 409 and "confirm" in r.json()["detail"]

    # 8. fill only: the form is filled, the sensitive question is left alone, nothing is sent
    fill = (await client.post(f"/api/browser/run/{draft['id']}", json={"headless": True})).json()
    plan = {p["label"].replace("*", "").strip(): p for p in fill["form_plan"]}
    assert plan["First Name"]["result"] == "done" and plan["Email"]["result"] == "done"
    assert plan["Resume"]["action"] == "upload" and plan["Resume"]["result"] == "done"
    assert plan["Gender"]["action"] == "sensitive" and plan["Gender"]["result"] == "left for you"
    assert fill["status"] == "filled_ready_for_review" and os.path.exists(fill["pre_submit_screenshot"])
    tracked = next(i for i in (await client.get("/api/applications", params={"page_size": 100})).json()["items"]
                   if i["job_id"] == job_id)
    assert tracked["stage"] not in ("submitted", "submission_unverified")
    assert not any("example.com" in l for l in fill["logs"])        # no personal data in the stored log

    # 9. submit with explicit confirmation: the site's confirmation is the evidence
    sub = (await client.post(f"/api/browser/run/{draft['id']}",
                             json={"auto_submit": True, "confirm_submit": True, "headless": True})).json()
    assert sub["status"] == "submitted", sub.get("intervention_reason")
    assert os.path.exists(sub["post_submit_screenshot"])

    # 10. tracker, history, report and backup all reflect it
    tracked = next(i for i in (await client.get("/api/applications", params={"page_size": 100})).json()["items"]
                   if i["job_id"] == job_id)
    assert tracked["stage"] == "submitted"
    events = (await client.get(f"/api/applications/{tracked['id']}/events")).json()
    assert [e["to_stage"] for e in events if e.get("to_stage")][-1] == "submitted"
    rep = (await client.get("/api/reports/daily")).json()["details_json"]["activity"]
    assert rep["submitted"] >= 1 and rep["drafts_prepared"] >= 1 and rep["new_jobs"] >= 1
    assert (await client.post(f"/api/applications/prepare/{job_id}", json={})).status_code == 409   # sent: never regenerated

    m = backup.create("acceptance")
    with zipfile.ZipFile(m["path"]) as z:
        names = z.namelist()
    assert any(n.startswith("resumes/") for n in names)
    assert any(n.startswith("screenshots/") for n in names)
    assert m["counts"]["applications"] >= 1


async def test_new_profile_defaults_to_prepare_only(client, monkeypatch, tmp_path):
    """Rule: default to PREPARE ONLY. A fresh install drafts applications but can't submit any."""
    import uuid
    from backend.database.db import AsyncSessionLocal
    from backend.database.models import Job
    from backend.services import profile_service as ps
    monkeypatch.setattr(ps.settings, "PROFILE_SEED_FILE", str(tmp_path / "no-seed.json"))
    prof = (await client.get("/api/profile")).json()
    assert prof["application_preferences"]["submission_policy"] == "prepare_only"

    jid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(Job(id=jid, company="Acme", title="Python Intern", url="https://example.com/apply", raw_text="Python",
                  source="manual_text"))
        await s.commit()
    d = (await client.post(f"/api/applications/prepare/{jid}", json={})).json()
    assert d["status"] == "drafted"
    assert not [a for a in (await client.get("/api/applications/approvals")).json() if a["draft_id"] == d["id"]]
    r = await client.post(f"/api/browser/run/{d['id']}", json={"auto_submit": True, "confirm_submit": True, "headless": True})
    assert r.status_code == 409 and "not been approved" in r.json()["detail"]
