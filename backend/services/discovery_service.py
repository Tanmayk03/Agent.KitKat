"""
Agent KitKat - Autonomous Job Discovery Service
Executes multi-source job hunting across public APIs and feeds,
detects and skips duplicates, runs deterministic eligibility verification,
performs resume matching, and triggers application preparation pipelines.
"""

import uuid
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Job, UserProfile, Resume, EligibilityResult, MatchResult
from backend.services.profile_service import ProfileService
from backend.services.resume_service import ResumeService
from backend.services.matching_service import MatchingService
from backend.services.application_service import ApplicationService
from backend.agents.job_reader import JobReaderAgent
from backend.agents.eligibility_agent import EligibilityAgent
from backend.agents.matching_agent import MatchingAgent
from backend.tools.duplicate_checker import DuplicateChecker
from backend.tools.job_discovery_sources import DISCOVERY_SOURCES
from backend.schemas.discovery import DiscoveryRunResult, DiscoveredJobItem, SourceStatusItem

logger = logging.getLogger("agent_kitkat.discovery_service")


class DiscoveryService:
    """
    Coordinates multi-source job discovery pipeline.
    """

    @staticmethod
    def get_sources_status() -> List[SourceStatusItem]:
        """List all configured discovery sources and their availability."""
        status_items = []
        for src in DISCOVERY_SOURCES:
            if src.name == "adzuna":
                import os
                is_conf = bool(os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"))
                desc = "Adzuna Job Search API (India). Requires free APP_ID & APP_KEY."
            elif src.name == "remotive":
                is_conf = True
                desc = "Remotive Free Public Developer & Intern API (Worldwide / Remote)."
            elif src.name == "jobicy":
                is_conf = True
                desc = "Jobicy Free Public Developer API (Remote tech jobs)."
            elif src.name == "curated_feed":
                is_conf = True
                desc = "Curated Indian Startup & Tech Internships feed."
            else:
                is_conf = True
                desc = "Custom job source."

            status_items.append(SourceStatusItem(
                source_name=src.name,
                is_configured=is_conf,
                description=desc
            ))
        return status_items

    @classmethod
    async def run_discovery(
        cls,
        db: AsyncSession,
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        limit_per_source: int = 5,
        auto_evaluate: bool = True,
        auto_prepare_applications: bool = True,
    ) -> DiscoveryRunResult:
        """
        Execute an autonomous multi-source job hunting cycle.
        """
        profile = await ProfileService.get_or_create_profile(db)
        search_keywords = keywords or profile.preferred_roles or ["Software Engineer Intern", "AI/ML Intern"]
        search_locations = locations or profile.preferred_locations or ["India", "Remote"]
        prefs = profile.application_preferences or {}
        min_score = float(prefs.get("min_match_score", 75))
        max_daily_apps = int(prefs.get("max_applications_per_day", 5))

        logger.info("Starting autonomous job discovery. Keywords: %s | Locations: %s", search_keywords, search_locations)

        discovered_raw: List[Dict[str, Any]] = []

        # 1. Fetch opportunities across all active discovery sources
        for source in DISCOVERY_SOURCES:
            try:
                src_results = await source.search(
                    keywords=search_keywords,
                    locations=search_locations,
                    limit=limit_per_source
                )
                discovered_raw.extend(src_results)
            except Exception as e:
                logger.error("Error fetching from source %s: %s", source.name, e)

        total_discovered = len(discovered_raw)
        new_saved = 0
        duplicates_skipped = 0
        eligible_count = 0
        shortlisted_count = 0
        prepared_count = 0
        processed_items: List[DiscoveredJobItem] = []

        # 2. Duplicate Detection & Persistence
        for item in discovered_raw:
            url = item.get("url")
            company = item.get("company", "Unknown")
            title = item.get("title", "Unknown Role")
            ext_id = item.get("job_id_external")

            is_dup, reason = await DuplicateChecker.check_duplicate(
                db=db,
                url=url,
                company=company,
                title=title,
                external_id=ext_id
            )

            if is_dup:
                duplicates_skipped += 1
                logger.info("Skipping duplicate: %s at %s (%s)", title, company, reason)
                continue

            # 3. Save New Opportunity
            job_obj = Job(
                id=str(uuid.uuid4()),
                company=company,
                title=title,
                url=url,
                location=item.get("location", "Not Specified"),
                work_mode=item.get("work_mode", "Remote"),
                source=item.get("source", "public_api"),
                job_id_external=ext_id,
                salary_stipend=item.get("salary_stipend"),
                description=item.get("description", ""),
                raw_text=item.get("raw_text", f"{title} at {company}"),
                status="discovered"
            )

            # Extract requirements using fast deterministic rules and known skills
            extracted = JobReaderAgent.extract_deterministic_features(job_obj.raw_text)
            job_obj.required_degree = extracted.get("required_degree")
            job_obj.graduation_eligibility = extracted.get("graduation_eligibility", [])
            job_obj.minimum_cgpa = extracted.get("minimum_cgpa")
            job_obj.required_skills = extracted.get("required_skills", [])
            job_obj.experience_required = "Fresher / Intern"

            db.add(job_obj)
            await db.commit()
            await db.refresh(job_obj)
            new_saved += 1

            elig_status = None
            match_score = None

            # 4. Auto-Evaluate (Eligibility & Resume Matching)
            if auto_evaluate:
                try:
                    eval_res = await MatchingService.evaluate_job(db, job_obj.id)
                    elig_status = eval_res.eligibility.overall_status
                    match_score = eval_res.overall_score

                    if elig_status == "PASS":
                        eligible_count += 1
                    if match_score >= min_score:
                        shortlisted_count += 1

                    # 5. Auto-Prepare Application if Qualifying
                    if auto_prepare_applications and elig_status == "PASS" and match_score >= min_score:
                        if prepared_count < max_daily_apps:
                            try:
                                draft = await ApplicationService.prepare_application(db, job_obj.id)
                                prepared_count += 1
                                logger.info("Application prepared for %s at %s (Draft: %s)", title, company, draft.id[:8])
                            except Exception as e:
                                logger.error("Failed to prepare application draft for job %s: %s", job_obj.id, e)
                except Exception as e:
                    logger.error("Error evaluating discovered job %s: %s", job_obj.id, e)

            processed_items.append(DiscoveredJobItem(
                job_id=job_obj.id,
                title=job_obj.title,
                company=job_obj.company,
                url=job_obj.url,
                source=job_obj.source,
                eligibility_status=elig_status,
                match_score=match_score,
                is_duplicate=False
            ))

        logger.info(
            "Discovery cycle complete: Found %d, Saved %d, Duplicates %d, Eligible %d, Shortlisted %d, Prepared %d",
            total_discovered, new_saved, duplicates_skipped, eligible_count, shortlisted_count, prepared_count
        )

        return DiscoveryRunResult(
            total_discovered=total_discovered,
            new_saved=new_saved,
            duplicates_skipped=duplicates_skipped,
            eligible_count=eligible_count,
            shortlisted_count=shortlisted_count,
            prepared_count=prepared_count,
            jobs=processed_items
        )
