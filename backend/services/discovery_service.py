"""
Agent KitKat - Autonomous Job Discovery Service

One discovery run:
  1. fetches every enabled source (public feeds + the company career boards you follow),
     isolating failures per source and recording a SourceRun row for each (source health);
  2. records expiry evidence reported by sources (closed flags / complete board snapshots);
  3. de-duplicates (source+ID, URL, company+title+location), refreshing last_seen_at on repeats;
  4. stores new listings with their source timestamps and deterministic requirements;
  5. evaluates eligibility + match, and drafts applications for PASS jobs above your threshold
     (never submits anything);
  6. stores a DiscoveryRun row with totals and progress so the dashboard can poll it.
"""

import re
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, desc, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Job, DiscoveryRun, SourceRun
from backend.services.profile_service import ProfileService
from backend.services.matching_service import MatchingService
from backend.services.application_service import ApplicationService
from backend.agents.job_reader import JobReaderAgent
from backend.tools.duplicate_checker import DuplicateChecker
from backend.tools.http_fetch import SourceFetchError
from backend.tools.job_discovery_sources import DISCOVERY_SOURCES, INDIA_LOCATION_PATTERNS, BaseDiscoverySource
from backend.tools.career_boards import build_board_sources
from backend.schemas.discovery import DiscoveryRunResult, DiscoveredJobItem, SourceStatusItem, SourceRunResult

logger = logging.getLogger("agent_kitkat.discovery_service")

# Job statuses that are still "just an opportunity" and may be flipped to expired
EXPIRABLE_STATUSES = ("discovered", "analyzed", "shortlisted", "rejected")


def _utcnow() -> datetime:
    return datetime.utcnow()


class DiscoveryService:
    """Coordinates the multi-source job discovery pipeline."""

    # ------------------------------------------------------------------ sources
    @staticmethod
    async def all_sources(db: AsyncSession) -> List[BaseDiscoverySource]:
        profile = await ProfileService.get_or_create_profile(db)
        boards = (profile.application_preferences or {}).get("career_boards") or []
        return list(DISCOVERY_SOURCES) + build_board_sources(boards)

    @classmethod
    async def get_sources_status(cls, db: AsyncSession) -> List[SourceStatusItem]:
        """List every source (public feeds + followed career boards) and whether it is configured."""
        return [
            SourceStatusItem(source_name=src.name, is_configured=src.is_configured(), description=src.description)
            for src in await cls.all_sources(db)
        ]

    # ------------------------------------------------------------------ expiry
    @staticmethod
    async def _mark_expired(db: AsyncSession, jobs: List[Job], evidence: str) -> int:
        now = _utcnow()
        count = 0
        for job in jobs:
            if job.expired_at is not None:
                continue
            job.expired_at = now
            job.expiry_evidence = evidence[:255]
            if job.status in EXPIRABLE_STATUSES:
                job.status = "expired"
            count += 1
        return count

    @classmethod
    async def _apply_expiry_evidence(cls, db: AsyncSession, source: BaseDiscoverySource) -> int:
        expired = 0
        if source.expired_external_ids:
            rows = (await db.execute(select(Job).where(
                Job.source == source.name,
                Job.job_id_external.in_(list(source.expired_external_ids)),
                Job.expired_at.is_(None),
            ))).scalars().all()
            expired += await cls._mark_expired(db, rows, f"{source.name} marks this listing as closed")
        if source.snapshot_scope is not None and source.snapshot_ids is not None:
            rows = (await db.execute(select(Job).where(
                Job.source == source.name,
                Job.job_id_external.like(f"{source.snapshot_scope}%"),
                Job.expired_at.is_(None),
            ))).scalars().all()
            gone = [j for j in rows if j.job_id_external not in source.snapshot_ids]
            expired += await cls._mark_expired(db, gone, f"No longer listed on {source.name}")
        if expired:
            await db.commit()
        return expired

    # ------------------------------------------------------------------ run
    @classmethod
    async def create_run_record(cls, db: AsyncSession, trigger: str) -> str:
        run = DiscoveryRun(id=str(uuid.uuid4()), trigger=trigger, status="running", progress="Starting...")
        db.add(run)
        await db.commit()
        return run.id

    @classmethod
    async def run_discovery(
        cls,
        db: AsyncSession,
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        limit_per_source: int = 5,
        auto_evaluate: bool = True,
        auto_prepare_applications: bool = True,
        trigger: str = "manual",
        run_id: Optional[str] = None,
    ) -> DiscoveryRunResult:
        """Execute one discovery cycle and persist its history."""
        from backend.services.halt import ensure_not_halted
        await ensure_not_halted(db)
        if run_id is None:
            run_id = await cls.create_run_record(db, trigger)
        run = (await db.execute(select(DiscoveryRun).where(DiscoveryRun.id == run_id))).scalars().first()

        async def progress(text: str) -> None:
            run.progress = text[:255]
            await db.commit()

        try:
            return await cls._run(db, run, progress, keywords, locations, limit_per_source,
                                  auto_evaluate, auto_prepare_applications)
        except Exception as e:
            await db.rollback()
            run.status = "failed"
            run.error = str(e)[:2000]
            run.finished_at = _utcnow()
            run.progress = "Failed"
            await db.commit()
            raise

    @classmethod
    async def _run(cls, db, run, progress, keywords, locations, limit_per_source,
                   auto_evaluate, auto_prepare_applications) -> DiscoveryRunResult:
        profile = await ProfileService.get_or_create_profile(db)
        search_keywords = keywords or profile.preferred_roles or ["Software Engineer Intern"]
        search_locations = locations or profile.preferred_locations or ["India", "Remote"]
        prefs = profile.application_preferences or {}
        min_score = float(prefs.get("min_match_score", 75))
        max_daily_apps = int(prefs.get("max_applications_per_day", 5))

        sources = await cls.all_sources(db)
        logger.info("Discovery run %s: %d sources.", run.id[:8], len(sources))

        discovered_raw: List[Dict[str, Any]] = []
        source_results: Dict[str, SourceRunResult] = {}
        source_rows: Dict[str, SourceRun] = {}
        expired_total = 0

        # 1. Fetch every source; one failing source never stops the others
        for idx, source in enumerate(sources, start=1):
            await progress(f"Fetching {source.name} ({idx}/{len(sources)})")
            started = time.perf_counter()
            row = SourceRun(id=str(uuid.uuid4()), run_id=run.id, source_name=source.name, started_at=_utcnow())
            source_rows[source.name] = row
            db.add(row)
            if not source.is_configured():
                res = SourceRunResult(source_name=source.name, ok=True, skipped_reason="Not configured")
            else:
                source.reset_run_state()
                try:
                    items = await source.search(keywords=search_keywords, locations=search_locations, limit=limit_per_source)
                    for item in items:
                        item["source"] = source.name
                    discovered_raw.extend(items)
                    res = SourceRunResult(source_name=source.name, ok=True, fetched=len(items))
                    res.expired = await cls._apply_expiry_evidence(db, source)
                    expired_total += res.expired
                except Exception as e:
                    logger.error("Source %s failed: %s", source.name, e)
                    res = SourceRunResult(source_name=source.name, ok=False, error=str(e)[:500])
                    if isinstance(e, SourceFetchError):
                        row.http_status = e.status_code
            res.duration_ms = round((time.perf_counter() - started) * 1000, 1)
            source_results[source.name] = res

        # India first, then international remote
        def geo_priority_key(item: Dict[str, Any]) -> int:
            loc = (item.get("location") or "").lower()
            return 0 if any(re.search(p, loc) for p in INDIA_LOCATION_PATTERNS) else 1

        discovered_raw.sort(key=geo_priority_key)

        new_saved = duplicates_skipped = eligible_count = shortlisted_count = prepared_count = item_errors = 0
        processed_items: List[DiscoveredJobItem] = []

        # 2. De-duplicate & store (errors isolated per listing)
        for n, item in enumerate(discovered_raw, start=1):
            if n == 1 or n % 5 == 0:
                await progress(f"Processing listings ({n}/{len(discovered_raw)})")
            src_name = item.get("source") or "unknown"
            src_stat = source_results.get(src_name)
            try:
                url, company, title = item.get("url"), item.get("company"), item.get("title")
                if not company or not title or not url:
                    continue
                ext_id = item.get("job_id_external")
                existing = await DuplicateChecker.find_existing(
                    db, url=url, company=company, title=title, external_id=ext_id,
                    source=src_name, location=item.get("location"),
                )
                if existing is not None:
                    job, reason = existing
                    duplicates_skipped += 1
                    if src_stat:
                        src_stat.duplicates += 1
                    if job.source == src_name:
                        job.last_seen_at = _utcnow()  # still listed by its source
                        await db.commit()
                    logger.debug("Duplicate: %s at %s (%s)", title, company, reason)
                    continue

                now = _utcnow()
                job_obj = Job(
                    id=str(uuid.uuid4()),
                    company=company,
                    title=title,
                    url=url,
                    location=item.get("location") or "Not stated",
                    work_mode=item.get("work_mode") or "Unknown",
                    source=src_name,
                    job_id_external=ext_id,
                    salary_stipend=item.get("salary_stipend"),
                    employment_type=item.get("employment_type"),
                    posted_at=item.get("posted_at"),
                    fetched_at=now,
                    last_seen_at=now,
                    description=item.get("description", ""),
                    raw_text=item.get("raw_text") or f"{title} at {company}",
                    status="discovered",
                )
                extracted = JobReaderAgent.extract_deterministic_features(job_obj.raw_text, title=title)
                job_obj.required_degree = extracted.get("required_degree")
                job_obj.graduation_eligibility = extracted.get("graduation_eligibility", [])
                job_obj.minimum_cgpa = extracted.get("minimum_cgpa")
                job_obj.required_skills = extracted.get("required_skills", [])
                job_obj.experience_required = extracted.get("experience_required")

                db.add(job_obj)
                await db.commit()
                await db.refresh(job_obj)
                new_saved += 1
                if src_stat:
                    src_stat.new_saved += 1
            except Exception as e:
                await db.rollback()
                item_errors += 1
                logger.exception("Could not store listing from %s: %s", src_name, e)
                continue

            elig_status = match_score = None
            if auto_evaluate:
                try:
                    eval_res = await MatchingService.evaluate_job(db, job_obj.id)
                    elig_status, match_score = eval_res.eligibility.overall_status, eval_res.overall_score
                    if elig_status == "PASS":
                        eligible_count += 1
                        if match_score >= min_score:
                            shortlisted_count += 1
                    if (auto_prepare_applications and elig_status == "PASS" and match_score >= min_score
                            and prepared_count < max_daily_apps):
                        try:
                            await ApplicationService.prepare_application(db, job_obj.id)
                            prepared_count += 1
                        except Exception as e:
                            await db.rollback()
                            logger.error("Failed to prepare draft for job %s: %s", job_obj.id, e)
                except Exception as e:
                    await db.rollback()
                    item_errors += 1
                    logger.error("Error evaluating job %s: %s", job_obj.id, e)

            processed_items.append(DiscoveredJobItem(
                job_id=job_obj.id, title=job_obj.title, company=job_obj.company, url=job_obj.url,
                source=job_obj.source, eligibility_status=elig_status, match_score=match_score,
            ))

        # 3. Persist source health + run summary
        for name, res in source_results.items():
            row = source_rows[name]
            row.ok, row.fetched, row.new_saved = res.ok, res.fetched, res.new_saved
            row.duplicates, row.expired_marked = res.duplicates, res.expired
            row.error, row.skipped_reason, row.duration_ms = res.error, res.skipped_reason, res.duration_ms

        attempted = [r for r in source_results.values() if not r.skipped_reason]
        failed = sum(1 for r in attempted if not r.ok)
        result = DiscoveryRunResult(
            run_id=run.id,
            total_discovered=len(discovered_raw),
            new_saved=new_saved,
            duplicates_skipped=duplicates_skipped,
            expired_marked=expired_total,
            eligible_count=eligible_count,
            shortlisted_count=shortlisted_count,
            prepared_count=prepared_count,
            failed_sources=failed,
            item_errors=item_errors,
            source_results=list(source_results.values()),
            jobs=processed_items,
        )
        run.status = "failed" if attempted and failed == len(attempted) else ("partial" if failed else "success")
        run.finished_at = _utcnow()
        run.total_fetched, run.new_saved, run.duplicates = len(discovered_raw), new_saved, duplicates_skipped
        run.expired_marked, run.failed_sources = expired_total, failed
        run.eligible_count, run.shortlisted_count, run.prepared_count = eligible_count, shortlisted_count, prepared_count
        run.progress = "Done"
        run.result_json = result.model_dump(mode="json", exclude={"jobs"})
        await db.commit()

        logger.info(
            "Discovery run %s %s: fetched %d, new %d, duplicates %d, expired %d, failed sources %d",
            run.id[:8], run.status, len(discovered_raw), new_saved, duplicates_skipped, expired_total, failed,
        )
        return result

    # ------------------------------------------------------------------ health / history
    @classmethod
    async def source_health(cls, db: AsyncSession, history: int = 10) -> List[Dict[str, Any]]:
        """Per-source health summary built from SourceRun history and stored jobs."""
        sources = await cls.all_sources(db)
        job_counts = {
            (src, status): n for src, status, n in (await db.execute(
                select(Job.source, Job.status, func.count(Job.id)).group_by(Job.source, Job.status)
            )).all()
        }
        since = _utcnow() - timedelta(hours=24)
        out = []
        for src in sources:
            runs = (await db.execute(
                select(SourceRun).where(SourceRun.source_name == src.name)
                .order_by(desc(SourceRun.started_at)).limit(history)
            )).scalars().all()
            attempted = [r for r in runs if not r.skipped_reason]
            last = runs[0] if runs else None
            last_ok = next((r for r in runs if r.ok and not r.skipped_reason), None)
            new_24h = (await db.execute(
                select(func.count(Job.id)).where(Job.source == src.name, Job.fetched_at >= since)
            )).scalar_one()
            if last is None:
                last_status = "never_run"
            elif last.skipped_reason:
                last_status = "skipped"
            else:
                last_status = "ok" if last.ok else "failed"
            out.append({
                "source_name": src.name,
                "description": src.description,
                "is_configured": src.is_configured(),
                "last_run_at": last.started_at.isoformat() if last else None,
                "last_status": last_status,
                "last_error": last.error if last and not last.ok else None,
                "last_success_at": last_ok.started_at.isoformat() if last_ok else None,
                "last_fetched": last.fetched if last else 0,
                "last_new": last.new_saved if last else 0,
                "last_duplicates": last.duplicates if last else 0,
                "last_expired": last.expired_marked if last else 0,
                "success_rate": round(sum(1 for r in attempted if r.ok) / len(attempted), 2) if attempted else None,
                "runs_considered": len(attempted),
                "jobs_total": sum(n for (s, _), n in job_counts.items() if s == src.name),
                "jobs_expired": job_counts.get((src.name, "expired"), 0),
                "new_last_24h": new_24h,
            })
        return out

    @staticmethod
    def run_to_dict(run: DiscoveryRun) -> Dict[str, Any]:
        return {
            "run_id": run.id, "trigger": run.trigger, "status": run.status, "progress": run.progress,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "total_fetched": run.total_fetched or 0, "new_saved": run.new_saved or 0,
            "duplicates": run.duplicates or 0, "expired_marked": run.expired_marked or 0,
            "failed_sources": run.failed_sources or 0, "eligible_count": run.eligible_count or 0,
            "shortlisted_count": run.shortlisted_count or 0, "prepared_count": run.prepared_count or 0,
            "error": run.error,
            "source_results": (run.result_json or {}).get("source_results", []),
        }

    @classmethod
    async def list_runs(cls, db: AsyncSession, limit: int = 20) -> List[Dict[str, Any]]:
        runs = (await db.execute(select(DiscoveryRun).order_by(desc(DiscoveryRun.started_at)).limit(limit))).scalars().all()
        return [cls.run_to_dict(r) for r in runs]

    @classmethod
    async def get_run(cls, db: AsyncSession, run_id: str) -> Optional[Dict[str, Any]]:
        run = (await db.execute(select(DiscoveryRun).where(DiscoveryRun.id == run_id))).scalars().first()
        return cls.run_to_dict(run) if run else None

    @staticmethod
    async def mark_interrupted_runs(db: AsyncSession) -> None:
        """At startup: runs left 'running' by a crash/restart are marked failed (honest history)."""
        await db.execute(
            update(DiscoveryRun).where(DiscoveryRun.status == "running")
            .values(status="failed", error="Interrupted (app restarted while running)", finished_at=_utcnow())
        )
        await db.commit()
