"""
Phase 5 Verification Tests for Agent KitKat.
Tests (Application Preparation & Approval Workflow):
1. Prepare application draft with Policy A (Manual Approval):
   - Tailored cover letter generation (grounded in verified facts).
   - Screening answers generation.
   - Profile form field mapping.
   - Pending approval request creation.
2. Edit application draft (cover letter / custom answers).
3. Human approval decision (Approve/Reject flow).
4. Prepare application draft with Policy B (Pre-authorized Automatic Submission).
5. Prepare application draft with Policy C (Prepare Only).
6. Application tracker listing.
7. Negative validation tests.
"""

import os
import sys
import asyncio
import httpx
from sqlalchemy import delete

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests._isolation  # noqa: E402,F401  -- throwaway DB; never touches your real data

from backend.main import app
from backend.database.db import init_db, AsyncSessionLocal
from backend.database.models import (
    UserProfile,
    Resume,
    Job,
    EligibilityResult,
    MatchResult,
    ApplicationDraft,
    ApprovalRequest,
    Application
)
from tests.test_phase2 import create_test_pdf_bytes


async def run_phase5_tests():
    print("==================================================")
    print("🚀 Starting Agent KitKat Phase 5 Verification Tests")
    print("==================================================")

    # Initialize DB
    await init_db()

    # Reset tables for clean, reproducible test suite
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Application))
        await session.execute(delete(ApprovalRequest))
        await session.execute(delete(ApplicationDraft))
        await session.execute(delete(MatchResult))
        await session.execute(delete(EligibilityResult))
        await session.execute(delete(Job))
        await session.execute(delete(Resume))
        await session.execute(delete(UserProfile))
        await session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

        # ----------------------------------------------------
        # Setup: Profile, Active Resume, and Eligible Job
        # ----------------------------------------------------
        print("\n[Setup] Initializing Profile and Uploading Candidate Resume...")
        profile_res = await client.get("/api/profile")
        assert profile_res.status_code == 200

        # Update profile with full contact details
        await client.put("/api/profile", json={
            "full_name": "Harshit Sharma",
            "email": "harshit.sharma@srm.edu",
            "phone": "+91 9876543210",
            "location": "Delhi NCR, India",
            "linkedin_url": "https://linkedin.com/in/harshit-sharma",
            "github_url": "https://github.com/harshit-sharma",
            "portfolio_url": "https://harshit-portfolio.dev"
        })

        pdf_bytes = create_test_pdf_bytes()
        files = {"file": ("harshit_sde_resume.pdf", pdf_bytes, "application/pdf")}
        upload_res = await client.post("/api/resumes/upload", files=files)
        assert upload_res.status_code == 200

        # Create eligible test job
        job_payload = {
            "title": "Software Engineer Intern",
            "company": "CloudScale Technologies",
            "text": """
            Company: CloudScale Technologies
            Role: Software Engineer Intern
            Location: Bangalore (Remote options)
            Eligibility:
            - Degree: B.Tech in Computer Science or Data Science
            - Batches: 2026 and 2027 batch
            - Minimum CGPA: 7.5
            Skills Required: Python, FastAPI, React, SQL, Docker.
            Stipend: ₹40,000 / month
            """
        }
        job_res = await client.post("/api/jobs/analyze-text", json=job_payload)
        assert job_res.status_code == 200
        job_id = job_res.json()["id"]
        print(f"Created Test Job ID: {job_id}")

        # ----------------------------------------------------
        # Test 1: Prepare Application (Policy A: Manual Approval)
        # ----------------------------------------------------
        print("\n[Test 1] Testing Prepare Application with Policy A (Manual Approval)...")
        prep_payload = {
            "policy_override": "manual_approval"
        }
        res = await client.post(f"/api/applications/prepare/{job_id}", json=prep_payload)
        assert res.status_code == 200, f"Error: {res.text}"
        draft_data = res.json()
        draft_id = draft_data["id"]

        print(f"Draft ID: {draft_id}")
        print(f"Draft Status: {draft_data['status']}")
        print(f"Policy Applied: {draft_data['policy_applied']}")
        print(f"Form Field Values: {draft_data['form_field_values']}")
        print(f"Custom Answers: {list(draft_data['custom_answers'].keys())}")
        print(f"\n--- Tailored Cover Letter Preview ---\n{draft_data['cover_letter'][:300]}...\n-------------------------------------")

        assert draft_data["status"] == "pending_approval"
        assert draft_data["form_field_values"]["full_name"] == "Harshit Sharma"
        assert draft_data["form_field_values"]["email"] == "harshit.sharma@srm.edu"
        assert draft_data["form_field_values"]["degree"] == "B.Tech"
        assert len(draft_data["cover_letter"]) > 100
        assert "why_join" in draft_data["custom_answers"]
        print("✅ Test 1 Passed: Application prepared with tailored cover letter and mapped form fields.")

        # ----------------------------------------------------
        # Test 2: Edit Application Draft
        # ----------------------------------------------------
        print("\n[Test 2] Testing Edit Application Draft (PUT /api/applications/drafts/{id})...")
        updated_letter = draft_data["cover_letter"] + "\n\nP.S. Excited to contribute to the core backend team!"
        edit_payload = {
            "cover_letter": updated_letter
        }
        edit_res = await client.put(f"/api/applications/drafts/{draft_id}", json=edit_payload)
        assert edit_res.status_code == 200
        edited_draft = edit_res.json()
        assert "Excited to contribute to the core backend team!" in edited_draft["cover_letter"]
        print("✅ Test 2 Passed: Draft cover letter edited and persisted.")

        # ----------------------------------------------------
        # Test 3: Approvals Listing and Decision
        # ----------------------------------------------------
        print("\n[Test 3] Testing Approvals List & Human Decision Flow...")
        appr_list_res = await client.get("/api/applications/approvals")
        assert appr_list_res.status_code == 200
        pending_list = appr_list_res.json()
        print(f"Pending Approvals Count: {len(pending_list)}")
        assert len(pending_list) >= 1
        approval_id = pending_list[0]["id"]
        assert pending_list[0]["company"] == "CloudScale Technologies"

        # Stage 5: approval is refused while placeholders / unverified claims remain -> fill them in first
        blocked = await client.post(f"/api/applications/approvals/{approval_id}/decide", json={"action": "approve"})
        assert blocked.status_code == 409
        fill = await client.put(f"/api/applications/drafts/{pending_list[0]['draft_id']}", json={"custom_answers": {
            "why_join": "I want to work on CloudScale's backend platform.",
            "relevant_project": "A FastAPI service I built for a college project.",
            "availability": "From June 2026",
            "salary_expectation": "As per company norms",
        }})
        assert fill.status_code == 200 and fill.json()["grounding_report"] == [], fill.json()["grounding_report"]

        # Approve the application
        decide_payload = {
            "action": "approve",
            "decision_notes": "Reviewed and approved by candidate."
        }
        decide_res = await client.post(f"/api/applications/approvals/{approval_id}/decide", json=decide_payload)
        assert decide_res.status_code == 200
        decision_data = decide_res.json()
        assert decision_data["status"] == "approved"

        # Verify draft status is now approved
        draft_check = await client.get(f"/api/applications/drafts/{draft_id}")
        assert draft_check.json()["status"] == "approved"
        print("✅ Test 3 Passed: Pending approval reviewed and approved successfully.")

        # ----------------------------------------------------
        # Test 4: Policy B (Pre-authorized Automatic Submission)
        # ----------------------------------------------------
        print("\n[Test 4] Testing Policy B (Pre-authorized Automatic Submission)...")
        prep_b_payload = {
            "policy_override": "pre_authorized"
        }
        res_b = await client.post(f"/api/applications/prepare/{job_id}", json=prep_b_payload)
        assert res_b.status_code == 200
        draft_b = res_b.json()
        print(f"Pre-authorized Draft Status: {draft_b['status']}")
        # Stage 2 safety change: every submission needs an explicit per-application approval,
        # so the legacy pre_authorized policy now queues for manual approval instead of auto-approving.
        assert draft_b["status"] == "pending_approval"
        assert draft_b["policy_applied"] == "manual_approval"
        print("✅ Test 4 Passed: pre_authorized no longer bypasses human approval.")

        # ----------------------------------------------------
        # Test 5: Policy C (Prepare Only)
        # ----------------------------------------------------
        print("\n[Test 5] Testing Policy C (Prepare Only)...")
        prep_c_payload = {
            "policy_override": "prepare_only"
        }
        res_c = await client.post(f"/api/applications/prepare/{job_id}", json=prep_c_payload)
        assert res_c.status_code == 200
        draft_c = res_c.json()
        print(f"Prepare-Only Draft Status: {draft_c['status']}")
        assert draft_c["status"] == "drafted"
        assert draft_c["policy_applied"] == "prepare_only"
        print("✅ Test 5 Passed: Policy C created prepared draft without automated trigger.")

        # ----------------------------------------------------
        # Test 6: Application Tracker
        # ----------------------------------------------------
        print("\n[Test 6] Testing Application Tracker (GET /api/applications/tracker)...")
        tracker_res = await client.get("/api/applications/tracker")
        assert tracker_res.status_code == 200
        tracked_apps = tracker_res.json()
        print(f"Tracked Applications Count: {len(tracked_apps)}")
        assert len(tracked_apps) >= 1
        print(f"Tracked App #1: {tracked_apps[0]['company']} - {tracked_apps[0]['role']} | Status: {tracked_apps[0]['status']}")
        print("✅ Test 6 Passed: Application tracker populated and verified.")

        # ----------------------------------------------------
        # Test 7: Negative Validation
        # ----------------------------------------------------
        print("\n[Test 7] Testing Negative Validation...")
        bad_draft = await client.get("/api/applications/drafts/non-existent-uuid")
        assert bad_draft.status_code == 404

        bad_appr = await client.post("/api/applications/approvals/non-existent-uuid/decide", json={"action": "approve"})
        assert bad_appr.status_code == 404
        print("✅ Test 7 Passed: Negative cases handled properly.")

    print("\n==================================================")
    print("🎉 ALL PHASE 5 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_phase5_tests())
