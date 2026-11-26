"""
Agent KitKat - Phase 6 Verification Test Suite
Tests Playwright browser automation agent, form field auto-filling,
resume uploading, tailored cover letter pasting, CAPTCHA/bot-wall safety pauses,
login-wall pauses, pre/post submission screenshot captures, emergency stop,
and screenshot retrieval API endpoints.
"""

import os
import sys
import uuid
import time
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import tests._isolation  # noqa: E402,F401  -- throwaway DB; never touches your real data

from backend.main import app
from backend.config import get_settings
from backend.database.db import AsyncSessionLocal, init_db
from backend.database.models import UserProfile, Resume, Job, ApplicationDraft, Application, EligibilityResult, MatchResult, ApprovalRequest
from backend.services.profile_service import ProfileService

settings = get_settings()


# ==============================================================================
# MOCK ATS & CHALLENGE HTTP SERVER
# ==============================================================================

STANDARD_FORM_HTML = """<!DOCTYPE html>
<html>
<head><title>CloudScale Technologies - Careers Application</title></head>
<body>
    <h2>Apply for Software Engineer Intern</h2>
    <div id="content">
        <form id="job-form" method="POST" action="/submit-success" enctype="multipart/form-data">
            <label>First Name: <input type="text" name="first_name" id="first_name" required /></label><br/><br/>
            <label>Last Name: <input type="text" name="last_name" id="last_name" required /></label><br/><br/>
            <label>Email: <input type="email" name="email" id="email" required /></label><br/><br/>
            <label>Phone: <input type="tel" name="phone" id="phone" /></label><br/><br/>
            <label>Location: <input type="text" name="location" id="location" /></label><br/><br/>
            <label>LinkedIn: <input type="text" name="linkedin_url" id="linkedin" /></label><br/><br/>
            <label>GitHub: <input type="text" name="github_url" id="github" /></label><br/><br/>
            <label>University: <input type="text" name="university" id="university" /></label><br/><br/>
            <label>Degree: <input type="text" name="degree" id="degree" /></label><br/><br/>
            <label>Graduation Year: <input type="text" name="graduation_year" id="grad_year" /></label><br/><br/>
            <label>CGPA: <input type="text" name="cgpa" id="cgpa" /></label><br/><br/>

            <p>Are you authorized to work in India?</p>
            <label><input type="radio" name="work_authorization" value="yes" id="auth_yes" /> Yes</label>
            <label><input type="radio" name="work_authorization" value="no" id="auth_no" /> No</label><br/><br/>

            <p>Will you now or in the future require visa sponsorship?</p>
            <label><input type="radio" name="requires_sponsorship" value="yes" id="spons_yes" /> Yes</label>
            <label><input type="radio" name="requires_sponsorship" value="no" id="spons_no" /> No</label><br/><br/>

            <label>Upload Resume: <input type="file" name="resume" id="resume_file" /></label><br/><br/>
            <label>Cover Letter:<br/>
                <textarea name="cover_letter" id="cover_letter" rows="6" cols="60"></textarea>
            </label><br/><br/>

            <label>Why do you want to join us?<br/>
                <input type="text" name="why_join" id="why_join" size="60" />
            </label><br/><br/>

            <button type="submit" id="submit-btn">Submit Application</button>
        </form>
    </div>

    <script>
        document.getElementById('job-form').addEventListener('submit', function(e) {
            e.preventDefault();
            document.getElementById('content').innerHTML = '<div id="success-banner"><h1>Thank you for applying!</h1><p>Your application has been received successfully.</p></div>';
        });
    </script>
</body>
</html>
"""

CAPTCHA_PAGE_HTML = """<!DOCTYPE html>
<html>
<head><title>Security Verification Required</title></head>
<body>
    <h2>Security Check</h2>
    <p>Please complete the security check to prove you are not a robot.</p>
    <iframe src="https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile" title="Turnstile"></iframe>
    <div class="cf-turnstile"></div>
</body>
</html>
"""

LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html>
<head><title>Sign in to Your Account</title></head>
<body>
    <h2>Candidate Login Required</h2>
    <p>You must sign in to apply for this job opportunity.</p>
    <form action="/login" method="POST">
        <input type="text" name="username" placeholder="Username" /><br/>
        <input type="password" name="password" placeholder="Password" /><br/>
        <button type="submit">Sign in</button>
    </form>
</body>
</html>
"""

UNFILLED_REQUIRED_HTML = """<!DOCTYPE html>
<html>
<head><title>Application Form with Declarations</title></head>
<body>
    <h2>Internship Application</h2>
    <form id="decl-form">
        <label>First Name: <input type="text" name="first_name" required /></label><br/><br/>
        <label>Email: <input type="email" name="email" required /></label><br/><br/>
        <label><input type="checkbox" name="mandatory_background_check_consent" id="bg_check" required /> I certify and consent to a mandatory background verification check.</label><br/><br/>
        <button type="submit">Submit</button>
    </form>
</body>
</html>
"""


class MockATSHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/standard-ats-job":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(STANDARD_FORM_HTML.encode("utf-8"))
        elif self.path == "/captcha-job":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(CAPTCHA_PAGE_HTML.encode("utf-8"))
        elif self.path == "/login-job" or "/login" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(LOGIN_PAGE_HTML.encode("utf-8"))
        elif self.path == "/unfilled-required-job":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(UNFILLED_REQUIRED_HTML.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h1>Thank you for applying!</h1><p>Your application received.</p>")

    def log_message(self, format, *args):
        # Silence standard HTTP logs to keep test output clean
        pass


# ==============================================================================
# INTEGRATION TESTS
# ==============================================================================

async def setup_test_db(base_url: str):
    """Seed test database with user profile, resume, and test jobs."""
    await init_db()

    async with AsyncSessionLocal() as session:
        # Clear existing records
        await session.execute(delete(Application))
        await session.execute(delete(ApprovalRequest))
        await session.execute(delete(ApplicationDraft))
        await session.execute(delete(MatchResult))
        await session.execute(delete(EligibilityResult))
        await session.execute(delete(Job))
        await session.execute(delete(Resume))
        await session.execute(delete(UserProfile))
        await session.commit()

        # Initialize Profile
        await ProfileService.get_or_create_profile(session)

        # Create dummy PDF resume on disk
        resumes_dir = settings.RESUMES_DIR
        os.makedirs(resumes_dir, exist_ok=True)
        dummy_resume_path = os.path.join(resumes_dir, "test_resume.pdf")
        with open(dummy_resume_path, "wb") as f:
            f.write(b"%PDF-1.4 mock resume content for playwright upload testing")

        resume = Resume(
            id=str(uuid.uuid4()),
            file_name="harshit_sde_resume.pdf",
            file_path=dummy_resume_path,
            file_size_bytes=len(b"%PDF-1.4 mock resume content for playwright upload testing"),
            file_type="pdf",
            raw_text="Harshit Sharma Python React Java Web Development",
            structured_data={"skills": ["Python", "React", "Java"]},
            is_active=True
        )
        session.add(resume)

        # Create Jobs for testing different browser scenarios
        job_standard = Job(
            id=str(uuid.uuid4()),
            company="CloudScale Technologies",
            title="Software Engineer Intern",
            url=f"{base_url}/standard-ats-job",
            raw_text="Software Engineer Intern CloudScale Technologies"
        )
        session.add(job_standard)

        job_captcha = Job(
            id=str(uuid.uuid4()),
            company="Protected Corp",
            title="Cloud Security Intern",
            url=f"{base_url}/captcha-job",
            raw_text="Cloud Security Intern Protected Corp"
        )
        session.add(job_captcha)

        job_login = Job(
            id=str(uuid.uuid4()),
            company="Enterprise Systems",
            title="Full Stack Intern",
            url=f"{base_url}/login-job",
            raw_text="Full Stack Intern Enterprise Systems"
        )
        session.add(job_login)

        job_required = Job(
            id=str(uuid.uuid4()),
            company="Compliance First",
            title="Data Intern",
            url=f"{base_url}/unfilled-required-job",
            raw_text="Data Intern Compliance First"
        )
        session.add(job_required)

        # Create ApplicationDrafts
        draft_standard = ApplicationDraft(
            id=str(uuid.uuid4()),
            job_id=job_standard.id,
            resume_id=resume.id,
            cover_letter="Dear Hiring Manager,\nI am excited to apply for the Software Engineer Intern role at CloudScale Technologies. My strong background in Python and web development makes me an ideal fit.",
            custom_answers={"why_join": "I am inspired by CloudScale's mission in modern cloud architectures."},
            form_field_values={
                "first_name": "Harshit",
                "last_name": "Sharma",
                "full_name": "Harshit Sharma",
                "email": "test.candidate@example.com",
                "phone": "+91 9876543210",
                "location": "Delhi NCR, India",
                "linkedin_url": "https://linkedin.com/in/harshit-sharma",
                "github_url": "https://github.com/harshit-sharma",
                "university": "SRM University, Delhi NCR",
                "degree": "B.Tech",
                "graduation_year": "2027",
                "cgpa": "8.44"
            },
            status="approved"
        )
        session.add(draft_standard)

        draft_captcha = ApplicationDraft(
            id=str(uuid.uuid4()),
            job_id=job_captcha.id,
            resume_id=resume.id,
            cover_letter="Cover letter for Protected Corp",
            form_field_values={"email": "test.candidate@example.com"},
            status="approved"
        )
        session.add(draft_captcha)

        draft_login = ApplicationDraft(
            id=str(uuid.uuid4()),
            job_id=job_login.id,
            resume_id=resume.id,
            cover_letter="Cover letter for Enterprise Systems",
            form_field_values={"email": "test.candidate@example.com"},
            status="approved"
        )
        session.add(draft_login)

        draft_required = ApplicationDraft(
            id=str(uuid.uuid4()),
            job_id=job_required.id,
            resume_id=resume.id,
            cover_letter="Cover letter for Compliance First",
            form_field_values={"first_name": "Harshit", "email": "test.candidate@example.com"},
            status="approved"
        )
        session.add(draft_required)
        await session.flush()

        # Stage 2: submission requires an APPROVED approval request per draft
        for d in (draft_standard, draft_captcha, draft_login, draft_required):
            session.add(ApprovalRequest(id=str(uuid.uuid4()), job_id=d.job_id, draft_id=d.id, status="approved"))

        await session.commit()

        return {
            "resume_id": resume.id,
            "draft_standard_id": draft_standard.id,
            "draft_captcha_id": draft_captcha.id,
            "draft_login_id": draft_login.id,
            "draft_required_id": draft_required.id,
        }


async def run_phase6_tests():
    print("==================================================")
    print("🚀 Starting Agent KitKat Phase 6 Verification Tests")
    print("==================================================")

    # Start mock server
    server = HTTPServer(("127.0.0.1", 0), MockATSHandler)
    host, port = server.server_address
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://{host}:{port}"
    print(f"[Setup] Mock ATS Server running at {base_url}")

    ids = await setup_test_db(base_url)
    draft_std_id = ids["draft_standard_id"]
    draft_cap_id = ids["draft_captcha_id"]
    draft_log_id = ids["draft_login_id"]
    draft_req_id = ids["draft_required_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:

        # ----------------------------------------------------------------------
        # TEST 1: Form Filling in Review Mode (auto_submit=False)
        # ----------------------------------------------------------------------
        print("\n[Test 1] Testing Application Form Auto-Filling (Review Mode: auto_submit=False)...")
        res1 = await client.post(
            f"/api/browser/run/{draft_std_id}",
            json={"auto_submit": False, "headless": True}
        )
        assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
        data1 = res1.json()
        assert data1["status"] == "filled_ready_for_review"
        assert data1["requires_human_intervention"] is True
        assert data1["pre_submit_screenshot"] is not None
        assert os.path.exists(data1["pre_submit_screenshot"])
        assert os.path.getsize(data1["pre_submit_screenshot"]) > 0

        # Check that logs record field filling, radio checks, resume upload, cover letter
        logs_str = " ".join(data1["logs"])
        # Stage 6: fields are matched by their LABELS; logs name the field, never the value
        assert "Filled 'First Name" in logs_str
        assert "Filled 'Email" in logs_str
        assert "test.candidate@example.com" not in logs_str  # personal values are never written to logs
        assert "Uploaded resume to" in logs_str
        assert "Filled 'Cover Letter" in logs_str
        plan = {f["label"].rstrip(":"): f for f in data1["form_plan"]}
        assert plan["Are you authorized to work in India?"]["action"] == "sensitive"
        assert plan["Will you now or in the future require visa sponsorship?"]["action"] == "sensitive"
        print(f"Pre-submit screenshot verified ({os.path.getsize(data1['pre_submit_screenshot'])} bytes)")
        print(f"Status: {data1['status']}")
        print("✅ Test 1 Passed: Form filled, resume uploaded, cover letter pasted, pre-submit screenshot saved.")

        # ----------------------------------------------------------------------
        # TEST 2: Form Submission in Auto-Submit Mode (auto_submit=True)
        # ----------------------------------------------------------------------
        print("\n[Test 2] Testing Application Form Auto-Submission & Confirmation (auto_submit=True)...")
        res2 = await client.post(
            f"/api/browser/run/{draft_std_id}",
            json={"auto_submit": True, "confirm_submit": True, "headless": True}
        )
        assert res2.status_code == 200, f"Expected 200, got {res2.status_code}: {res2.text}"
        data2 = res2.json()
        assert data2["status"] == "submitted"
        assert data2["requires_human_intervention"] is False
        assert data2["post_submit_screenshot"] is not None
        assert os.path.exists(data2["post_submit_screenshot"])
        assert os.path.getsize(data2["post_submit_screenshot"]) > 0

        logs2_str = " ".join(data2["logs"])
        assert "Website confirmed submission" in logs2_str
        print(f"Post-submit screenshot verified ({os.path.getsize(data2['post_submit_screenshot'])} bytes)")
        print(f"Status: {data2['status']}")
        print("✅ Test 2 Passed: Application submitted and confirmed by website.")

        # ----------------------------------------------------------------------
        # TEST 3: Anti-Bot / CAPTCHA Detection Safety Check
        # ----------------------------------------------------------------------
        print("\n[Test 3] Testing CAPTCHA / Anti-Bot Detection Safety Pause...")
        res3 = await client.post(
            f"/api/browser/run/{draft_cap_id}",
            json={"auto_submit": True, "confirm_submit": True, "headless": True}
        )
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["status"] == "paused_captcha"
        assert data3["requires_human_intervention"] is True
        assert "CAPTCHA" in data3["intervention_reason"]
        print(f"Intervention Reason: {data3['intervention_reason']}")
        print("✅ Test 3 Passed: Zero-bypass rule respected. Agent paused on CAPTCHA challenge.")

        # ----------------------------------------------------------------------
        # TEST 4: Login Gate Detection Safety Check
        # ----------------------------------------------------------------------
        print("\n[Test 4] Testing Login Wall Detection Safety Pause...")
        res4 = await client.post(
            f"/api/browser/run/{draft_log_id}",
            json={"auto_submit": True, "confirm_submit": True, "headless": True}
        )
        assert res4.status_code == 200
        data4 = res4.json()
        assert data4["status"] == "paused_login"
        assert data4["requires_human_intervention"] is True
        print(f"Intervention Reason: {data4['intervention_reason']}")
        print("✅ Test 4 Passed: Agent paused safely when authentication is required.")

        # ----------------------------------------------------------------------
        # TEST 5: Unfilled Mandatory Fields / Declarations Safety Check
        # ----------------------------------------------------------------------
        print("\n[Test 5] Testing Unfilled Required Field / Legal Declaration Safety Pause...")
        res5 = await client.post(
            f"/api/browser/run/{draft_req_id}",
            json={"auto_submit": True, "confirm_submit": True, "headless": True}
        )
        assert res5.status_code == 200
        data5 = res5.json()
        assert data5["status"] == "paused_unknown_field"
        assert data5["requires_human_intervention"] is True
        assert "background verification" in data5["intervention_reason"]  # reported by its label
        print(f"Intervention Reason: {data5['intervention_reason']}")
        print("✅ Test 5 Passed: Agent refused to guess sensitive declaration; paused for human decision.")

        # ----------------------------------------------------------------------
        # TEST 6: Emergency Stop & Status Queries
        # ----------------------------------------------------------------------
        print("\n[Test 6] Testing Emergency Stop & Live Status...")
        status_res = await client.get("/api/browser/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert "is_active" in status_data

        stop_res = await client.post("/api/browser/emergency-stop")
        assert stop_res.status_code == 200
        stop_data = stop_res.json()
        assert stop_data["status"] == "emergency_stopped"
        print("✅ Test 6 Passed: Emergency stop and status endpoints verified.")

        # ----------------------------------------------------------------------
        # TEST 7: Screenshot Retrieval Endpoint
        # ----------------------------------------------------------------------
        print("\n[Test 7] Testing Screenshot Retrieval Endpoint (GET /api/browser/screenshots/...)...")
        img_res = await client.get(f"/api/browser/screenshots/{draft_std_id}/pre_submit.png")
        assert img_res.status_code == 200
        assert img_res.headers["content-type"] == "image/png"
        assert len(img_res.content) > 0

        # Negative test: non-existent screenshot
        bad_img = await client.get(f"/api/browser/screenshots/{draft_std_id}/non_existent.png")
        assert bad_img.status_code == 404
        print(f"Image retrieved successfully: {len(img_res.content)} bytes")
        print("✅ Test 7 Passed: Screenshot retrieval endpoint validated.")

    server.shutdown()
    server.server_close()

    print("\n==================================================")
    print("🎉 ALL PHASE 6 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_phase6_tests())
