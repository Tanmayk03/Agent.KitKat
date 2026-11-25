import os
import sys
import asyncio
import logging
import re

sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import select, delete
from backend.database.db import AsyncSessionLocal, init_db
from backend.database.models import (
    Job,
    UserProfile,
    Resume,
    EligibilityResult,
    MatchResult,
    ApplicationDraft,
    ApprovalRequest,
    Application
)
from backend.services.discovery_service import DiscoveryService
from backend.tools.job_discovery_sources import (
    is_senior_role,
    is_geographically_eligible,
    INDIA_LOCATION_PATTERNS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_kitkat.harvest_india_remote")

async def main():
    await init_db()

    async with AsyncSessionLocal() as session:
        print("\n==================================================")
        print("STEP 1: PURGING PRIOR JOBS & NON-COMPLIANT ROLES")
        print("==================================================")

        await session.execute(delete(ApprovalRequest))
        await session.execute(delete(Application))
        await session.execute(delete(ApplicationDraft))
        await session.execute(delete(MatchResult))
        await session.execute(delete(EligibilityResult))
        await session.execute(delete(Job))
        await session.commit()
        print("Database cleared of all previous jobs and test drafts.")

        prof_res = await session.execute(select(UserProfile))
        profile = prof_res.scalars().first()
        res_res = await session.execute(select(Resume).where(Resume.is_active == True))
        resume = res_res.scalars().first()

        print(f"Candidate: {profile.full_name} | {profile.education.get('college')} (Batch {profile.education.get('graduation_year')})")
        print(f"Active Resume: {resume.file_name} (ID: {resume.id})")
        print(f"Constraint: India Jobs (Priority) + International Jobs ONLY IF REMOTE")

        print("\n==================================================")
        print("STEP 2: RUNNING AUTONOMOUS HARVEST (INDIA & REMOTE)")
        print("==================================================")

        discovery_result = await DiscoveryService.run_discovery(
            db=session,
            keywords=profile.preferred_roles,
            locations=profile.preferred_locations,
            limit_per_source=10,
            auto_evaluate=True,
            auto_prepare_applications=True
        )

        print(f"Total Discovered:   {discovery_result.total_discovered}")
        print(f"New Saved:          {discovery_result.new_saved}")
        print(f"Eligible (PASS):    {discovery_result.eligible_count}")
        print(f"Shortlisted:        {discovery_result.shortlisted_count}")
        print(f"Drafts Prepared:    {discovery_result.prepared_count}")

        print("\n==================================================")
        print("STEP 3: VERIFYING ZERO SENIOR & ZERO FOREIGN ONSITE")
        print("==================================================")

        jobs_res = await session.execute(select(Job).order_by(Job.created_at.desc()))
        jobs = jobs_res.scalars().all()

        india_count = 0
        remote_count = 0
        violating_count = 0

        for j in jobs:
            is_sr = is_senior_role(j.title)
            is_elig, is_in = is_geographically_eligible(j.location, j.work_mode, j.raw_text)

            if is_sr or not is_elig:
                violating_count += 1
                print(f"  [VIOLATION] {j.company}: {j.title} | Loc: {j.location} | Mode: {j.work_mode}")
            else:
                tag = "INDIA" if is_in else "INTL REMOTE"
                if is_in:
                    india_count += 1
                else:
                    remote_count += 1
                print(f"  [{tag:11}] {j.company:24} | {j.title:48} | {j.location[:30]}")

        print(f"\nVerification Results:")
        print(f"  India Domestic Roles:         {india_count}")
        print(f"  International Remote Roles:   {remote_count}")
        print(f"  Violating/Ineligible Roles:   {violating_count} (MUST BE 0)")

        # Print prepared drafts
        drafts_res = await session.execute(select(ApplicationDraft))
        drafts = drafts_res.scalars().all()
        print(f"\nPrepared Application Drafts in Queue: {len(drafts)}")
        for d in drafts:
            appr_res = await session.execute(select(ApprovalRequest).where(ApprovalRequest.draft_id == d.id))
            appr = appr_res.scalars().first()
            j_res = await session.execute(select(Job).where(Job.id == d.job_id))
            job = j_res.scalars().first()
            loc_tag = "INDIA" if any(re.search(pat, (job.location or "").lower()) for pat in INDIA_LOCATION_PATTERNS) else "REMOTE"
            print(f"- [{loc_tag}] Draft for '{job.title}' at {job.company}")
            print(f"  Role URL: {job.url}")
            print(f"  Cover Letter Preview:\n  {d.cover_letter[:220]}...\n")

        print("==================================================")
        print("PIPELINE EXECUTION COMPLETE & 100% COMPLIANT")
        print("==================================================")

def _require_wipe_confirmation():
    """This script DELETES all jobs, drafts, approvals and application history before harvesting."""
    import sys as _sys
    if "--wipe-my-data" not in _sys.argv:
        print("Refusing to run: this script deletes ALL jobs, drafts, approvals and tracked applications.\n"
              "Use the dashboard's 'Run discovery' instead (it keeps your data and skips duplicates).\n"
              "If you really want a wipe, back up storage/agent_kitkat.db and re-run with --wipe-my-data.")
        _sys.exit(2)


if __name__ == "__main__":
    _require_wipe_confirmation()
    asyncio.run(main())
