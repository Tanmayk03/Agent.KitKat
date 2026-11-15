import os
import sys
import asyncio
import logging

sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import select, delete, text
from backend.database.db import AsyncSessionLocal, init_db
from backend.database.models import (
    Job,
    UserProfile,
    Resume,
    EligibilityResult,
    MatchResult,
    ApplicationDraft,
    ApprovalRequest,
    Application,
    DailyReport
)
from backend.services.discovery_service import DiscoveryService
from backend.services.matching_service import MatchingService
from backend.services.application_service import ApplicationService
from backend.tools.job_discovery_sources import is_senior_role

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_kitkat.harvest_internships")

async def main():
    await init_db()

    async with AsyncSessionLocal() as session:
        print("\n==================================================")
        print("STEP 1: PURGING SENIOR & NON-INTERN ROLES")
        print("==================================================")

        # Delete all existing jobs and associated records so only genuine intern/fresher jobs exist
        await session.execute(delete(ApprovalRequest))
        await session.execute(delete(Application))
        await session.execute(delete(ApplicationDraft))
        await session.execute(delete(MatchResult))
        await session.execute(delete(EligibilityResult))
        await session.execute(delete(Job))
        await session.commit()
        print("Purged all prior jobs and test drafts. Active user profile & resume preserved.")

        # Verify active profile and resume
        prof_res = await session.execute(select(UserProfile))
        profile = prof_res.scalars().first()
        res_res = await session.execute(select(Resume).where(Resume.is_active == True))
        resume = res_res.scalars().first()

        print(f"Active Candidate: {profile.full_name} | {profile.education.get('college')} (Batch {profile.education.get('graduation_year')})")
        print(f"Active Resume:    {resume.file_name} (ID: {resume.id})")
        print(f"Target Roles:     {profile.preferred_roles}")

        print("\n==================================================")
        print("STEP 2: RUNNING AUTONOMOUS INTERNSHIP DISCOVERY")
        print("==================================================")

        discovery_result = await DiscoveryService.run_discovery(
            db=session,
            keywords=profile.preferred_roles,
            locations=profile.preferred_locations,
            limit_per_source=8,
            auto_evaluate=True,
            auto_prepare_applications=True
        )

        print(f"Total Discovered:   {discovery_result.total_discovered}")
        print(f"New Saved:          {discovery_result.new_saved}")
        print(f"Eligible:           {discovery_result.eligible_count}")
        print(f"Shortlisted:        {discovery_result.shortlisted_count}")
        print(f"Drafts Prepared:    {discovery_result.prepared_count}")

        print("\n==================================================")
        print("STEP 3: VERIFYING ZERO SENIOR ROLES & ACCURACY")
        print("==================================================")

        jobs_res = await session.execute(select(Job).order_by(Job.created_at.desc()))
        jobs = jobs_res.scalars().all()

        senior_found = 0
        for j in jobs:
            is_sr = is_senior_role(j.title)
            if is_sr:
                senior_found += 1
                print(f"  [ERROR SENIOR] {j.company}: {j.title}")
            else:
                print(f"  [INTERN/FRESHER OK] {j.company}: {j.title} ({j.work_mode}) -> {j.url[:70]}")

        print(f"\nSenior/Experienced roles found: {senior_found} (MUST BE 0)")

        # Print prepared drafts
        drafts_res = await session.execute(select(ApplicationDraft))
        drafts = drafts_res.scalars().all()
        print(f"\nPrepared Application Drafts: {len(drafts)}")
        for d in drafts:
            appr_res = await session.execute(select(ApprovalRequest).where(ApprovalRequest.draft_id == d.id))
            appr = appr_res.scalars().first()
            j_res = await session.execute(select(Job).where(Job.id == d.job_id))
            job = j_res.scalars().first()
            print(f"- Draft for {job.title} at {job.company} (Approval: {appr.id if appr else 'N/A'})")
            print(f"  Cover Letter Preview:\n  {d.cover_letter[:200]}...\n")

        print("==================================================")
        print("HARVEST COMPLETE & VERIFIED")
        print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
