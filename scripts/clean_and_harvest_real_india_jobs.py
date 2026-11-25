import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.config import get_settings
from backend.database.models import Job, ApplicationDraft, ApprovalRequest, Application, MatchResult, EligibilityResult
from backend.tools.job_discovery_sources import (
    TechInternshipsDiscoverySource,
    JobicyDiscoverySource,
    RemotiveDiscoverySource,
    WeWorkRemotelyDiscoverySource,
    is_geographically_eligible,
    is_senior_role,
    classify_location
)
from backend.services.matching_service import MatchingService
from backend.services.application_service import ApplicationService

async def main():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    print("=== PURGING NON-COMPLIANT / FOREIGN NON-REMOTE / NON-TECH JOBS ===")
    async with session_maker() as session:
        all_jobs = (await session.execute(select(Job))).scalars().all()
        purged = 0
        kept = 0
        for job in all_jobs:
            elig, is_ind = is_geographically_eligible(job.location or "", job.work_mode or "")
            senior = is_senior_role(job.title)
            
            # Must be tech
            t_lower = job.title.lower()
            is_tech = any(k in t_lower for k in [
                "software", "developer", "engineer", "data", "ai", "machine learning",
                "frontend", "backend", "full stack", "cloud", "security", "web", "systems", "research"
            ])

            if (not elig) or senior or (not is_tech):
                purged += 1
                print(f"[PURGE] Deleting: '{job.company}' - '{job.title}' (Loc: {job.location})")
                await session.execute(delete(ApprovalRequest).where(ApprovalRequest.job_id == job.id))
                await session.execute(delete(Application).where(Application.job_id == job.id))
                await session.execute(delete(ApplicationDraft).where(ApplicationDraft.job_id == job.id))
                await session.execute(delete(MatchResult).where(MatchResult.job_id == job.id))
                await session.execute(delete(EligibilityResult).where(EligibilityResult.job_id == job.id))
                await session.delete(job)
            else:
                kept += 1
                print(f"[KEEP] '{job.company}' - '{job.title}' (Loc: {job.location})")
        
        await session.commit()
        print(f"Purge complete: {purged} purged, {kept} retained.\n")

    print("=== HARVESTING FRESH REAL LIVE TECH INTERNSHIPS (INDIA FIRST) ===")
    simplify_source = TechInternshipsDiscoverySource()
    fresh_jobs = await simplify_source.search([], [], limit=50)
    print(f"Discovered {len(fresh_jobs)} strictly filtered real jobs from SimplifyJobs feed.")

    async with session_maker() as session:
        added = 0
        for jdata in fresh_jobs:
            # Check duplicate by url
            existing = (await session.execute(select(Job).where(Job.url == jdata["url"]))).scalars().first()
            if existing:
                continue

            # Verify location again
            elig, is_ind = is_geographically_eligible(jdata.get("location") or "", jdata.get("work_mode") or "")
            if not elig:
                continue

            new_job = Job(
                company=jdata["company"],
                title=jdata["title"],
                url=jdata["url"],
                description=jdata.get("raw_text") or f"{jdata['title']} at {jdata['company']}",
                raw_text=jdata.get("raw_text") or "",
                location=jdata.get("location"),
                work_mode=jdata.get("work_mode") or "Unknown",
                employment_type=jdata.get("employment_type") or "Internship",
                source=jdata.get("source"),
                job_id_external=jdata.get("job_id_external"),
                posted_at=jdata.get("posted_at")
            )
            session.add(new_job)
            await session.flush()
            added += 1

            # Run deterministic matching and evaluation
            try:
                match_eval = await MatchingService.evaluate_job(session, new_job.id)
                # If high match (>= 70%) and India role, prepare draft
                if match_eval.overall_score >= 70.0 and is_ind:
                    await ApplicationService.prepare_application(session, new_job.id)
                    print(f"  [STAGED FOR APPROVAL] {new_job.company} - {new_job.title} ({match_eval.overall_score}%)")
            except Exception as e:
                print(f"  Evaluation error for {new_job.title}: {e}")

        await session.commit()
        print(f"Added {added} new compliant real tech internships to database.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
