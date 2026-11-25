"""
Phase 3 Verification Tests for Agent KitKat.
Tests (Mode B: Manual Job URL Analysis):
1. Analyze raw job description text (Qwen2.5 1.5B + deterministic parser).
2. Verify extraction of degree, graduation eligibility, CGPA, skills, work mode, and stipend.
3. Analyze uploaded job description PDF document.
4. Test URL reader error recovery and prompt for manual paste on inaccessible URLs.
5. List and retrieve analyzed jobs from database.
6. Negative validation tests.
"""

import os
import sys
import asyncio
import httpx

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests._isolation  # noqa: E402,F401  -- throwaway DB; never touches your real data

from backend.main import app
from backend.database.db import init_db
from tests.test_phase2 import create_test_pdf_bytes


SAMPLE_JOB_TEXT = """
Company: Nexus Innovations Pvt Ltd
Position: Software Engineer Intern (Full-Stack)
Location: Bangalore, India (Remote options available)
Stipend: ₹35,000 per month
Duration: 6 Months

About the Role:
We are looking for passionate undergraduate interns to join our engineering team.
You will work on full-stack web applications using Python and React.

Eligibility Criteria:
- Degree: B.Tech / B.E. in Computer Science, Data Science, or related fields.
- Eligible Batches: 2026 and 2027 graduating students only.
- Minimum Academic Cutoff: Minimum CGPA of 8.0 throughout engineering.

Required Technical Skills:
- Strong proficiency in Python and modern JavaScript / React.js.
- Familiarity with backend frameworks like FastAPI or Django.
- Experience with relational databases like SQL (PostgreSQL or MySQL).
- Basic understanding of Docker, Git, and REST APIs.

Perks:
- Flexible work hours, Certificate of Internship, Pre-Placement Offer (PPO) based on performance.
"""


async def run_phase3_tests():
    print("==================================================")
    print("🚀 Starting Agent KitKat Phase 3 Verification Tests")
    print("==================================================")

    # Initialize DB
    await init_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

        # ----------------------------------------------------
        # 1. Test Analyze Pasted Job Description Text
        # ----------------------------------------------------
        print("\n[Test 1] Testing Analyze Job Text (POST /api/jobs/analyze-text)...")
        payload = {
            "text": SAMPLE_JOB_TEXT,
            "title": "Software Engineer Intern",
            "company": "Nexus Innovations"
        }
        res = await client.post("/api/jobs/analyze-text", json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        job_1_id = data["id"]
        extracted = data["extracted"]

        print(f"Stored Job ID: {job_1_id}")
        print(f"Company: {extracted['company_name']}")
        print(f"Title: {extracted['job_title']}")
        print(f"Location: {extracted['work_location']} | Mode: {extracted['work_mode']}")
        print(f"Degree: {extracted['required_degree']}")
        print(f"Graduation Batches: {extracted['graduation_eligibility']}")
        print(f"Min CGPA: {extracted['minimum_cgpa']}")
        print(f"Required Skills: {extracted['required_skills']}")
        print(f"Salary / Stipend: {extracted['salary_or_stipend']}")
        print(f"Analysis Duration: {data['analysis_duration_ms']} ms")

        # Verify key extractions
        assert "Nexus" in extracted["company_name"]
        assert "Python" in extracted["required_skills"]
        assert "React" in extracted["required_skills"]
        assert "FastAPI" in extracted["required_skills"]
        assert "SQL" in extracted["required_skills"]
        assert 2027 in extracted["graduation_eligibility"]
        assert extracted["minimum_cgpa"] == 8.0
        assert extracted["work_mode"] in ["Remote", "Hybrid"]
        print("✅ Test 1 Passed: Pasted job description parsed and structured with local AI.")

        # ----------------------------------------------------
        # 2. Test Analyze Uploaded Job Description File (PDF)
        # ----------------------------------------------------
        print("\n[Test 2] Testing Analyze Job Document (POST /api/jobs/analyze-file)...")
        pdf_bytes = create_test_pdf_bytes()
        files = {
            "file": ("job_description_sde.pdf", pdf_bytes, "application/pdf")
        }
        res = await client.post("/api/jobs/analyze-file", files=files)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data_pdf = res.json()
        job_2_id = data_pdf["id"]
        extracted_pdf = data_pdf["extracted"]

        print(f"Uploaded JD Job ID: {job_2_id}")
        print(f"Skills from JD PDF: {extracted_pdf['required_skills']}")
        assert "Python" in extracted_pdf["required_skills"]
        assert data_pdf["source"] == "manual_file"
        print("✅ Test 2 Passed: Uploaded PDF job description parsed successfully.")

        # ----------------------------------------------------
        # 3. Test Inaccessible URL Handling (Requires Manual Paste)
        # ----------------------------------------------------
        print("\n[Test 3] Testing Inaccessible URL Handling (POST /api/jobs/analyze-url)...")
        # Testing a non-existent or localhost unreachable URL
        bad_url_payload = {
            "url": "http://127.0.0.1:59999/non-existent-career-link"
        }
        res = await client.post("/api/jobs/analyze-url", json=bad_url_payload)
        assert res.status_code == 200
        url_data = res.json()
        print(f"URL Result - Requires Manual Paste: {url_data['requires_manual_paste']}")
        print(f"User Message: {url_data['message']}")
        assert url_data["requires_manual_paste"] is True
        assert "paste" in url_data["message"].lower() or "connect" in url_data["message"].lower()
        print("✅ Test 3 Passed: Inaccessible URL cleanly prompts user for manual paste.")

        # ----------------------------------------------------
        # 4. Test Job Listing and Details Retrieval
        # ----------------------------------------------------
        print("\n[Test 4] Testing List Jobs and Get Job Details...")
        res = await client.get("/api/jobs")
        assert res.status_code == 200
        jobs_list = res.json()
        print(f"Total Analyzed Jobs in Database: {len(jobs_list)}")
        assert len(jobs_list) >= 2

        res = await client.get(f"/api/jobs/{job_1_id}")
        assert res.status_code == 200
        job_detail = res.json()
        assert job_detail["id"] == job_1_id
        assert job_detail["company"] == extracted["company_name"]
        assert job_detail["minimum_cgpa"] == 8.0
        print(f"Verified stored job details for ID: {job_1_id}")
        print("✅ Test 4 Passed: List and single job endpoints verified.")

        # ----------------------------------------------------
        # 5. Test Negative Cases
        # ----------------------------------------------------
        print("\n[Test 5] Testing Negative Validation Cases...")
        # Text too short
        bad_text_res = await client.post("/api/jobs/analyze-text", json={"text": "Short"})
        assert bad_text_res.status_code == 422
        print("Short text correctly rejected with 422.")

        # Unsupported file type
        bad_file_res = await client.post(
            "/api/jobs/analyze-file",
            files={"file": ("invalid.txt", b"plain text", "text/plain")}
        )
        assert bad_file_res.status_code == 400
        print("Unsupported .txt upload rejected with 400.")

        # Non-existent job
        non_existent_res = await client.get("/api/jobs/non-existent-uuid")
        assert non_existent_res.status_code == 404
        print("Non-existent job ID returned 404.")
        print("✅ Test 5 Passed: Negative cases handled properly.")

    print("\n==================================================")
    print("🎉 ALL PHASE 3 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_phase3_tests())
