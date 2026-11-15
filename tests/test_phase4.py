"""
Phase 4 Verification Tests for Agent KitKat.
Tests (Eligibility Verification & Resume Matching Engine):
1. Case A: Eligible Job with High Match Score (B.Tech 2027, CGPA 8.44, Python/React).
2. Case B: Mandatory Batch Failure Override (2024/2025 only - even with 100% skills, MUST BE INELIGIBLE).
3. Case C: Mandatory CGPA Failure Override (Cutoff 9.0 vs 8.44).
4. Case D: Strict UNKNOWN rule enforcement (Unknown information is never treated as a pass).
5. Rankings listing endpoint (GET /api/matching/rankings).
6. Negative 404 validation.
"""

import os
import sys
import asyncio
import httpx
from sqlalchemy import delete

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database.db import init_db, AsyncSessionLocal
from backend.database.models import UserProfile, Resume, Job, EligibilityResult, MatchResult
from tests.test_phase2 import create_test_pdf_bytes


async def run_phase4_tests():
    print("==================================================")
    print("🚀 Starting Agent KitKat Phase 4 Verification Tests")
    print("==================================================")

    # Initialize DB
    await init_db()

    # Reset tables for clean, reproducible test suite
    async with AsyncSessionLocal() as session:
        await session.execute(delete(MatchResult))
        await session.execute(delete(EligibilityResult))
        await session.execute(delete(Job))
        await session.execute(delete(Resume))
        await session.execute(delete(UserProfile))
        await session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

        # ----------------------------------------------------
        # Setup: Initialize Profile and Upload Active Resume
        # ----------------------------------------------------
        print("\n[Setup] Initializing Profile and Uploading Candidate Resume...")
        profile_res = await client.get("/api/profile")
        assert profile_res.status_code == 200

        pdf_bytes = create_test_pdf_bytes()
        files = {"file": ("candidate_sde_resume.pdf", pdf_bytes, "application/pdf")}
        upload_res = await client.post("/api/resumes/upload", files=files)
        assert upload_res.status_code == 200
        resume_data = upload_res.json()["resume"]
        print(f"Resume Uploaded and Active: {resume_data['id']}")

        # ----------------------------------------------------
        # Test 1: Eligible Job with High Compatibility
        # ----------------------------------------------------
        print("\n[Test 1] Testing Eligible Job with High Match...")
        job_eligible_payload = {
            "title": "Software Engineer Intern",
            "company": "TechNova Solutions",
            "text": """
            Company: TechNova Solutions
            Role: Software Engineer Intern
            Location: Bangalore (Remote friendly)
            Eligibility:
            - Degree: B.Tech in CS/IT
            - Graduation Batches: 2026 and 2027 batch
            - Minimum CGPA: 7.5
            Skills Required: Python, React, FastAPI, SQL, Docker, Git.
            """
        }
        res = await client.post("/api/jobs/analyze-text", json=job_eligible_payload)
        assert res.status_code == 200
        job_eligible_id = res.json()["id"]

        # Run Evaluation
        eval_res = await client.post(f"/api/matching/evaluate/{job_eligible_id}")
        assert eval_res.status_code == 200, f"Error: {eval_res.text}"
        eval_data = eval_res.json()

        print(f"Overall Score: {eval_data['overall_score']}%")
        print(f"Eligibility Status: {eval_data['eligibility']['overall_status']}")
        print(f"Recommendation: {eval_data['recommendation']}")
        print(f"Category Scores: {eval_data['category_scores']}")
        print(f"Matching Skills: {eval_data['matching_skills']}")

        assert eval_data["eligibility"]["overall_status"] == "PASS"
        assert eval_data["overall_score"] >= 80.0
        assert eval_data["recommendation"] == "STRONGLY_RECOMMENDED"
        assert "Python" in eval_data["matching_skills"]
        assert "React" in eval_data["matching_skills"]
        print("✅ Test 1 Passed: Highly compatible job correctly passed and recommended.")

        # ----------------------------------------------------
        # Test 2: Mandatory Batch Failure Override
        # ----------------------------------------------------
        print("\n[Test 2] Testing Mandatory Batch Failure Override (2024/2025 only)...")
        # Candidate has 100% of skills, but job is restricted to 2024/2025 only.
        job_batch_fail_payload = {
            "title": "Software Developer Intern",
            "company": "Legacy Corp",
            "text": """
            Company: Legacy Corp
            Role: Software Developer Intern
            Location: Remote
            Eligibility Criteria:
            - Strictly for 2024 and 2025 graduates only. 2026/2027 students are not eligible.
            - Degree: B.Tech
            - CGPA: 7.0
            Required Skills: Python, React, SQL.
            """
        }
        res = await client.post("/api/jobs/analyze-text", json=job_batch_fail_payload)
        assert res.status_code == 200
        job_batch_fail_id = res.json()["id"]

        eval_res = await client.post(f"/api/matching/evaluate/{job_batch_fail_id}")
        assert eval_res.status_code == 200
        eval_batch_data = eval_res.json()

        print(f"Overall Score: {eval_batch_data['overall_score']}%")
        print(f"Eligibility Status: {eval_batch_data['eligibility']['overall_status']}")
        print(f"Graduation Check: {eval_batch_data['eligibility']['graduation']}")
        print(f"Rejection Reasons: {eval_batch_data['eligibility']['rejection_reasons']}")
        print(f"Recommendation: {eval_batch_data['recommendation']}")

        assert eval_batch_data["eligibility"]["overall_status"] == "FAIL"
        assert eval_batch_data["eligibility"]["graduation"]["status"] == "FAIL"
        assert eval_batch_data["recommendation"] == "INELIGIBLE"
        assert len(eval_batch_data["eligibility"]["rejection_reasons"]) > 0
        print("✅ Test 2 Passed: Strict Rule Enforced - Hard batch failure overrode skills match.")

        # ----------------------------------------------------
        # Test 3: Mandatory CGPA Failure Override (Cutoff 9.0 vs 8.44)
        # ----------------------------------------------------
        print("\n[Test 3] Testing Mandatory CGPA Failure Override (Cutoff 9.0)...")
        job_cgpa_fail_payload = {
            "title": "Research Intern",
            "company": "Elite Labs",
            "text": """
            Company: Elite Labs
            Role: Research Intern
            Location: Remote
            Eligibility Criteria:
            - Minimum CGPA of 9.0 throughout B.Tech is strictly mandatory.
            - Eligible Batches: 2027 batch.
            Required Skills: Python, SQL.
            """
        }
        res = await client.post("/api/jobs/analyze-text", json=job_cgpa_fail_payload)
        assert res.status_code == 200
        job_cgpa_fail_id = res.json()["id"]

        eval_res = await client.post(f"/api/matching/evaluate/{job_cgpa_fail_id}")
        assert eval_res.status_code == 200
        eval_cgpa_data = eval_res.json()

        print(f"CGPA Check: {eval_cgpa_data['eligibility']['cgpa']}")
        print(f"Recommendation: {eval_cgpa_data['recommendation']}")

        assert eval_cgpa_data["eligibility"]["overall_status"] == "FAIL"
        assert eval_cgpa_data["eligibility"]["cgpa"]["status"] == "FAIL"
        assert eval_cgpa_data["recommendation"] == "INELIGIBLE"
        print("✅ Test 3 Passed: Strict Rule Enforced - CGPA cutoff failure correctly rejected.")

        # ----------------------------------------------------
        # Test 4: Strict UNKNOWN Rule Enforcement
        # ----------------------------------------------------
        print("\n[Test 4] Testing Strict UNKNOWN Rule Enforcement...")
        # Job description does not mention graduation batch at all
        job_unknown_payload = {
            "title": "Web Development Intern",
            "company": "StartupX",
            "text": """
            Company: StartupX
            Role: Web Development Intern
            Location: Remote
            We need a motivated intern to build web dashboards.
            Skills: React, Node.js, JavaScript, HTML, CSS.
            """
        }
        res = await client.post("/api/jobs/analyze-text", json=job_unknown_payload)
        assert res.status_code == 200
        job_unknown_id = res.json()["id"]

        eval_res = await client.post(f"/api/matching/evaluate/{job_unknown_id}")
        assert eval_res.status_code == 200
        eval_unk_data = eval_res.json()

        print(f"Overall Eligibility: {eval_unk_data['eligibility']['overall_status']}")
        print(f"Graduation Status: {eval_unk_data['eligibility']['graduation']['status']}")
        print(f"Unverified Requirements: {eval_unk_data['eligibility']['unverified_requirements']}")
        print(f"Recommendation: {eval_unk_data['recommendation']}")

        assert eval_unk_data["eligibility"]["graduation"]["status"] == "UNKNOWN"
        assert eval_unk_data["eligibility"]["overall_status"] == "UNKNOWN"
        assert len(eval_unk_data["eligibility"]["unverified_requirements"]) > 0
        assert eval_unk_data["recommendation"] in ["CONSIDER_WITH_VERIFICATION", "NEEDS_VERIFICATION"]
        print("✅ Test 4 Passed: Strict Rule Enforced - Unknown information was NEVER treated as a pass.")

        # ----------------------------------------------------
        # Test 5: Rankings Listing
        # ----------------------------------------------------
        print("\n[Test 5] Testing Rankings Listing (GET /api/matching/rankings)...")
        rankings_res = await client.get("/api/matching/rankings")
        assert rankings_res.status_code == 200
        rankings = rankings_res.json()
        print(f"Total Ranked Opportunities: {len(rankings)}")
        for idx, item in enumerate(rankings):
            print(f"#{idx+1}: {item['company']} - {item['title']} | Score: {item['overall_score']}% | Status: {item['eligibility_status']} | Rec: {item['recommendation']}")

        # Ensure sorted descending
        scores = [r["overall_score"] for r in rankings]
        assert scores == sorted(scores, reverse=True), "Rankings must be sorted in descending order!"
        # Eligible job must be above rejected ones
        assert rankings[0]["company"] == "TechNova Solutions"
        print("✅ Test 5 Passed: Rankings endpoint returned properly sorted opportunities.")

        # ----------------------------------------------------
        # Test 6: Negative Validation
        # ----------------------------------------------------
        print("\n[Test 6] Testing Negative Case (Non-existent Job)...")
        bad_eval = await client.post("/api/matching/evaluate/non-existent-uuid")
        assert bad_eval.status_code == 404
        print("Non-existent job correctly returned 404.")
        print("✅ Test 6 Passed: Negative validation verified.")

    print("\n==================================================")
    print("🎉 ALL PHASE 4 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_phase4_tests())
