"""
Agent KitKat - Phase 7 Verification Test Suite
Tests Mode A Autonomous Job Discovery, Multi-source APIs, Duplicate Detection,
Eligibility & Matching in discovery pipeline, Automated Application Preparation,
APScheduler recurring background jobs, and Real-data Daily Activity Reports.
"""

import os
import sys
import uuid
import asyncio
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app
from backend.config import get_settings
from backend.database.db import AsyncSessionLocal, init_db
from backend.database.models import (
    UserProfile,
    Resume,
    Job,
    EligibilityResult,
    MatchResult,
    ApplicationDraft,
    ApprovalRequest,
    Application,
    DailyReport
)
from backend.tools.duplicate_checker import DuplicateChecker
from backend.scheduler.daily_scheduler import daily_scheduler

settings = get_settings()


async def run_phase7_tests():
    print("==================================================")
    print("🚀 Starting Agent KitKat Phase 7 Verification Tests")
    print("==================================================")

    # Initialize DB & Tables
    await init_db()

    # Clear tables for fresh run
    async with AsyncSessionLocal() as session:
        await session.execute(delete(DailyReport))
        await session.execute(delete(Application))
        await session.execute(delete(ApprovalRequest))
        await session.execute(delete(ApplicationDraft))
        await session.execute(delete(MatchResult))
        await session.execute(delete(EligibilityResult))
        await session.execute(delete(Job))
        await session.execute(delete(Resume))
        await session.execute(delete(UserProfile))
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:

        # ----------------------------------------------------------------------
        # SETUP: Candidate Profile & Active Resume
        # ----------------------------------------------------------------------
        print("\n[Setup] Initializing Profile and Uploading Candidate Resume...")
        p_res = await client.get("/api/profile")
        assert p_res.status_code == 200

        await client.put("/api/profile", json={
            "full_name": "Harshit Sharma",
            "email": "harshit.sharma@srm.edu",
            "phone": "+91 9876543210",
            "location": "Delhi NCR, India",
            "preferred_roles": ["Software Engineer Intern", "Full Stack Developer Intern", "AI/ML Engineer Intern"],
            "preferred_locations": ["India", "Remote", "Noida", "Bangalore"],
            "application_preferences": {
                "daily_search_time": "09:00",
                "max_applications_per_day": 2,
                "min_match_score": 70,
                "submission_policy": "manual_approval"
            }
        })

        # Create active resume
        dummy_resume_path = os.path.join(settings.RESUMES_DIR, "phase7_resume.pdf")
        with open(dummy_resume_path, "wb") as f:
            f.write(b"%PDF-1.4 mock resume with Python React Java Web development Node.js")

        async with AsyncSessionLocal() as session:
            resume = Resume(
                id=str(uuid.uuid4()),
                file_name="phase7_resume.pdf",
                file_path=dummy_resume_path,
                file_size_bytes=len(b"%PDF-1.4 mock resume with Python React Java Web development Node.js"),
                file_type="pdf",
                raw_text="Harshit Sharma B.Tech CS & Data Science SRM University 2027 Python React Java Node.js Web development",
                structured_data={"skills": ["Python", "React", "Java", "Node.js", "Web development"]},
                is_active=True
            )
            session.add(resume)
            await session.commit()

        # ----------------------------------------------------------------------
        # TEST 1: Source Health & Configuration Status
        # ----------------------------------------------------------------------
        print("\n[Test 1] Testing Discovery Sources Endpoint (GET /api/discovery/sources)...")
        src_res = await client.get("/api/discovery/sources")
        assert src_res.status_code == 200
        sources = src_res.json()
        assert len(sources) >= 3
        source_names = [s["source_name"] for s in sources]
        assert "curated_feed" in source_names
        assert "remotive" in source_names
        print(f"Active Sources: {source_names}")
        print("✅ Test 1 Passed: Discovery sources cataloged and accessible.")

        # ----------------------------------------------------------------------
        # TEST 2: Autonomous Job Discovery Sweep
        # ----------------------------------------------------------------------
        print("\n[Test 2] Testing Autonomous Job Discovery Sweep (POST /api/discovery/search)...")
        disc_res = await client.post("/api/discovery/search", json={
            "keywords": ["Software Engineer Intern", "Full Stack Developer Intern"],
            "limit_per_source": 3,
            "auto_evaluate": True,
            "auto_prepare_applications": True
        })
        assert disc_res.status_code == 200
        disc_data = disc_res.json()
        assert disc_data["total_discovered"] > 0
        assert disc_data["new_saved"] > 0
        print(f"Total Discovered: {disc_data['total_discovered']}")
        print(f"New Saved: {disc_data['new_saved']}")
        print(f"Eligible Found: {disc_data['eligible_count']}")
        print(f"Shortlisted: {disc_data['shortlisted_count']}")
        print(f"Applications Prepared: {disc_data['prepared_count']}")
        assert disc_data["prepared_count"] <= 2  # Respects max_applications_per_day
        print("✅ Test 2 Passed: Discovery pipeline ingested, evaluated, and drafted qualifying jobs.")

        # ----------------------------------------------------------------------
        # TEST 3: Duplicate Detection Verification
        # ----------------------------------------------------------------------
        print("\n[Test 3] Testing Duplicate Detection Engine on Subsequent Sweep...")
        second_sweep = await client.post("/api/discovery/search", json={
            "keywords": ["Software Engineer Intern", "Full Stack Developer Intern"],
            "limit_per_source": 3,
            "auto_evaluate": True,
            "auto_prepare_applications": True
        })
        assert second_sweep.status_code == 200
        second_data = second_sweep.json()
        print(f"Second Sweep Total: {second_data['total_discovered']}")
        print(f"Duplicates Skipped: {second_data['duplicates_skipped']}")
        print(f"New Saved: {second_data['new_saved']}")
        assert second_data["duplicates_skipped"] > 0
        assert second_data["new_saved"] == 0  # Zero duplicate records created!

        # Direct unit test of DuplicateChecker
        async with AsyncSessionLocal() as session:
            is_dup, reason = await DuplicateChecker.check_duplicate(
                db=session,
                company="NexusAI Technologies Inc.",
                title="Software Engineer Intern (Python / React)"
            )
            assert is_dup is True
            print(f"Normalized duplicate detected: {reason}")
        print("✅ Test 3 Passed: Duplicate checker strictly prevented duplicate ingestion.")

        # ----------------------------------------------------------------------
        # TEST 4: Real-Data Daily Activity Report Generation
        # ----------------------------------------------------------------------
        print("\n[Test 4] Testing Daily Report Generation (GET /api/reports/daily)...")
        rep_res = await client.get("/api/reports/daily")
        assert rep_res.status_code == 200
        rep_data = rep_res.json()
        assert rep_data["total_discovered"] == disc_data["new_saved"]
        assert rep_data["new_found"] == disc_data["new_saved"]
        assert rep_data["prepared_count"] == disc_data["prepared_count"]
        assert "# 🍫 Agent KitKat - Daily Activity Report" in rep_data["summary_markdown"]
        print(f"Report Date: {rep_data['report_date']}")
        print(f"Total Discovered in DB: {rep_data['total_discovered']}")
        print(f"Report ID: {rep_data['id']}")
        print("--- Markdown Summary Snippet ---")
        print("\n".join(rep_data["summary_markdown"].split("\n")[:14]))
        print("--------------------------------")
        print("✅ Test 4 Passed: Daily report accurately reflects database state.")

        # ----------------------------------------------------------------------
        # TEST 5: Reports History and ID Lookup
        # ----------------------------------------------------------------------
        print("\n[Test 5] Testing Reports History & Single Report Lookup...")
        hist_res = await client.get("/api/reports/history")
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) >= 1
        assert history[0]["id"] == rep_data["id"]

        single_res = await client.get(f"/api/reports/{rep_data['id']}")
        assert single_res.status_code == 200
        assert single_res.json()["id"] == rep_data["id"]

        # Negative test for non-existent report
        bad_rep = await client.get("/api/reports/non-existent-uuid")
        assert bad_rep.status_code == 404
        print("✅ Test 5 Passed: Report history and ID retrieval verified.")

        # ----------------------------------------------------------------------
        # TEST 6: Background Scheduler Management
        # ----------------------------------------------------------------------
        print("\n[Test 6] Testing Scheduler Lifecycle (Start, Status, Trigger, Stop)...")
        start_res = await client.post("/api/scheduler/start?hour=9&minute=0")
        assert start_res.status_code == 200
        start_data = start_res.json()
        assert start_data["is_running"] is True
        assert start_data["scheduled_time"] == "09:00"

        stat_res = await client.get("/api/scheduler/status")
        assert stat_res.status_code == 200
        assert stat_res.json()["is_running"] is True

        # Test on-demand trigger
        trig_res = await client.post("/api/scheduler/trigger")
        assert trig_res.status_code == 200
        assert trig_res.json()["status"] == "success"

        # Stop scheduler
        stop_res = await client.post("/api/scheduler/stop")
        assert stop_res.status_code == 200
        assert stop_res.json()["is_running"] is False
        print("✅ Test 6 Passed: APScheduler start, on-demand trigger, and stop confirmed.")

    # Ensure scheduler is cleanly stopped
    daily_scheduler.stop()

    print("\n==================================================")
    print("🎉 ALL PHASE 7 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_phase7_tests())
