"""
Agent KitKat - Daily reports built only from stored records.

A report covers ONE calendar day in your timezone (settings.TIMEZONE, default Asia/Kolkata).
"Activity" numbers count only what happened during that day, using record timestamps
(fetched_at, evaluations, draft versions, lifecycle events, source runs). "Snapshot" numbers
(pending approvals, applications by stage, follow-ups due) describe the state right now and are
labelled as such.

GET is read-only (computed live). Saving a report (POST / end of each scheduled cycle) upserts
one row per date.
"""

import uuid
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import (
    Application, ApplicationEvent, ApprovalRequest, DailyReport, DiscoveryRun, DraftVersion,
    EligibilityResult, Job, MatchResult, SourceRun,
)
from backend.schemas.reporting import DailyReportResponse
from backend.services.lifecycle import STAGES, stage_label
from backend.services.profile_service import ProfileService

logger = logging.getLogger("agent_kitkat.reporting_service")
settings = get_settings()

FINAL_STAGES = {"rejected", "withdrawn", "offer_received", "not_eligible"}
RESPONSE_STAGES = ("assessment_received", "interview", "offer_received", "rejected")


def local_tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TIMEZONE)
    except Exception:
        logger.warning("Unknown TIMEZONE %r; using UTC. On Windows run: pip install tzdata", settings.TIMEZONE)
        return ZoneInfo("UTC")


def today_local() -> date:
    return datetime.now(local_tz()).date()


def day_window_utc(day: date) -> Tuple[datetime, datetime]:
    """[start, end) of a local calendar day, as naive UTC datetimes (how the DB stores times)."""
    tz = local_tz()
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    return start, end


def parse_day(value: Optional[str]) -> date:
    if not value:
        return today_local()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Date must be YYYY-MM-DD.")


class ReportingService:
    """Builds daily reports from database records only."""

    @staticmethod
    async def compute(db: AsyncSession, day: date) -> Dict[str, Any]:
        start, end = day_window_utc(day)
        in_day = lambda col: and_(col >= start, col < end)  # noqa: E731
        count = lambda q: db.execute(q)  # noqa: E731

        async def scalar(q) -> int:
            return int((await count(q)).scalar() or 0)

        profile = await ProfileService.get_or_create_profile(db)
        min_score = float((profile.application_preferences or {}).get("min_match_score", 75))

        # ---- activity during the day -------------------------------------------------
        runs = (await db.execute(select(DiscoveryRun).where(in_day(DiscoveryRun.started_at)))).scalars().all()
        listings_fetched = sum(r.total_fetched or 0 for r in runs)
        new_jobs = await scalar(select(func.count(Job.id)).where(in_day(func.coalesce(Job.fetched_at, Job.created_at))))
        expired_found = await scalar(select(func.count(Job.id)).where(in_day(Job.expired_at)))

        evals = (await db.execute(
            select(EligibilityResult.overall_status, MatchResult.overall_score)
            .outerjoin(MatchResult, MatchResult.job_id == EligibilityResult.job_id)
            .where(in_day(EligibilityResult.created_at))
        )).all()
        eligible = sum(1 for s, _ in evals if s == "PASS")
        ineligible = sum(1 for s, _ in evals if s == "FAIL")
        unknown = sum(1 for s, _ in evals if s == "UNKNOWN")
        above_threshold = sum(1 for s, sc in evals if s == "PASS" and (sc or 0) >= min_score)

        drafts_prepared = await scalar(select(func.count(DraftVersion.id)).where(
            DraftVersion.source == "generated", in_day(DraftVersion.created_at)))
        approvals_decided = await scalar(select(func.count(ApprovalRequest.id)).where(in_day(ApprovalRequest.decided_at)))

        events = (await db.execute(
            select(ApplicationEvent.to_stage, ApplicationEvent.from_stage).where(in_day(ApplicationEvent.created_at))
        )).all()
        moved_to = lambda *stages: sum(1 for to, fr in events if to in stages and to != fr)  # noqa: E731
        submitted = moved_to("submitted", "submission_unverified")
        shortlisted_by_you = moved_to("shortlisted")
        responses = {s: moved_to(s) for s in RESPONSE_STAGES}

        failed_rows = (await db.execute(
            select(SourceRun.source_name, SourceRun.error, SourceRun.started_at)
            .where(in_day(SourceRun.started_at), SourceRun.ok.is_(False))
            .order_by(desc(SourceRun.started_at))
        )).all()
        source_failures = [{"source": n, "error": (e or "")[:200], "at": t.isoformat()} for n, e, t in failed_rows]

        top_rows = (await db.execute(
            select(Job.id, Job.title, Job.company, Job.location, MatchResult.overall_score)
            .join(EligibilityResult, EligibilityResult.job_id == Job.id)
            .join(MatchResult, MatchResult.job_id == Job.id)
            .where(in_day(func.coalesce(Job.fetched_at, Job.created_at)), EligibilityResult.overall_status == "PASS")
            .order_by(desc(MatchResult.overall_score)).limit(5)
        )).all()
        top_new = [{"job_id": i, "title": t, "company": c, "location": l, "score": s} for i, t, c, l, s in top_rows]

        # ---- snapshot (now) --------------------------------------------------------------
        pending_approvals = await scalar(select(func.count(ApprovalRequest.id)).where(ApprovalRequest.status == "pending"))
        stage_counts = {k: v for k, v in (await db.execute(
            select(Application.stage, func.count(Application.id)).group_by(Application.stage))).all() if k}
        fu_rows = (await db.execute(
            select(Application.id, Application.follow_up_date, Application.stage, Job.company, Job.title)
            .join(Job, Job.id == Application.job_id)
            .where(Application.follow_up_date.isnot(None), Application.follow_up_date <= day.isoformat(),
                   Application.stage.notin_(FINAL_STAGES))
            .order_by(Application.follow_up_date)
        )).all()
        follow_ups = [{"application_id": i, "date": d, "stage": stage_label(s), "company": c, "title": t}
                      for i, d, s, c, t in fu_rows]

        return {
            "day": day.isoformat(),
            "timezone": str(local_tz()),
            "window_utc": [start.isoformat(), end.isoformat()],
            "activity": {
                "discovery_runs": len(runs),
                "discovery_runs_failed": sum(1 for r in runs if r.status == "failed"),
                "scheduled_runs": sum(1 for r in runs if r.trigger == "scheduled"),
                "listings_fetched": listings_fetched,
                "new_jobs": new_jobs,
                "expired_found": expired_found,
                "evaluated": len(evals),
                "eligible": eligible,
                "ineligible": ineligible,
                "unknown": unknown,
                "eligible_above_threshold": above_threshold,
                "shortlisted_by_you": shortlisted_by_you,
                "drafts_prepared": drafts_prepared,
                "approvals_decided": approvals_decided,
                "submitted": submitted,
                "responses": responses,
                "source_failures": len(source_failures),
            },
            "snapshot": {
                "pending_approvals": pending_approvals,
                "applications_by_stage": {stage_label(k): v for k, v in stage_counts.items()},
                "follow_ups_due": len(follow_ups),
            },
            "min_match_score": min_score,
            "source_failures": source_failures,
            "follow_ups": follow_ups,
            "top_new": top_new,
        }

    @staticmethod
    def to_markdown(d: Dict[str, Any]) -> str:
        a, s = d["activity"], d["snapshot"]
        lines = [
            f"# Agent KitKat daily report: {d['day']}",
            f"_Times in {d['timezone']}. Built only from records stored that day._",
            "",
            "## What happened",
            f"- Discovery runs: **{a['discovery_runs']}** ({a['scheduled_runs']} scheduled, {a['discovery_runs_failed']} failed); "
            f"listings fetched: **{a['listings_fetched']}**; new jobs stored: **{a['new_jobs']}**; expired found: {a['expired_found']}",
            f"- Evaluated: {a['evaluated']}: eligible **{a['eligible']}**, ineligible {a['ineligible']}, needs verification {a['unknown']}; "
            f"eligible and ≥ {d['min_match_score']:g}%: **{a['eligible_above_threshold']}**",
            f"- Shortlisted by you: {a['shortlisted_by_you']} · drafts prepared: {a['drafts_prepared']} · approvals decided: {a['approvals_decided']}",
            f"- Applications submitted: **{a['submitted']}**",
            "- Employer responses: " + ", ".join(f"{STAGES[k]} {v}" for k, v in a["responses"].items()),
            "",
            "## Right now",
            f"- Waiting for your approval: **{s['pending_approvals']}**",
            "- Applications by stage: " + (", ".join(f"{k} {v}" for k, v in s["applications_by_stage"].items()) or "none"),
        ]
        if d["follow_ups"]:
            lines += ["", "## Follow-ups due"] + [f"- {f['date']}: {f['title']} at {f['company']} ({f['stage']})" for f in d["follow_ups"]]
        if d["top_new"]:
            lines += ["", "## Best new eligible opportunities"] + [f"- {t['score']}%: {t['title']} at {t['company']}" for t in d["top_new"]]
        if d["source_failures"]:
            lines += ["", "## Source failures"] + [f"- {f['source']}: {f['error']}" for f in d["source_failures"]]
        return "\n".join(lines)

    @staticmethod
    def _response(day: date, d: Dict[str, Any], row: Optional[DailyReport] = None) -> DailyReportResponse:
        a, s = d["activity"], d["snapshot"]
        return DailyReportResponse(
            id=row.id if row else f"live-{day.isoformat()}",
            report_date=day.isoformat(),
            total_discovered=a["listings_fetched"],
            new_found=a["new_jobs"],
            eligible_count=a["eligible"],
            rejected_count=a["ineligible"],
            unknown_count=a["unknown"],
            shortlisted_count=a["eligible_above_threshold"],
            prepared_count=a["drafts_prepared"],
            submitted_count=a["submitted"],
            pending_approvals_count=s["pending_approvals"],
            failed_count=a["source_failures"],
            summary_markdown=ReportingService.to_markdown(d),
            details_json=d,
            created_at=row.created_at if row else datetime.utcnow(),
        )

    @staticmethod
    async def get_daily_report(db: AsyncSession, target_date: Optional[str] = None) -> DailyReportResponse:
        """Read-only: computed live from records."""
        day = parse_day(target_date)
        return ReportingService._response(day, await ReportingService.compute(db, day))

    @staticmethod
    async def generate_daily_report(db: AsyncSession, target_date: Optional[str] = None) -> DailyReportResponse:
        """Compute and save (one row per date; re-saving replaces it)."""
        day = parse_day(target_date)
        d = await ReportingService.compute(db, day)
        resp = ReportingService._response(day, d)
        row = (await db.execute(select(DailyReport).where(DailyReport.report_date == day.isoformat()))).scalars().first()
        if row is None:
            row = DailyReport(id=str(uuid.uuid4()), report_date=day.isoformat(), created_at=datetime.utcnow())
            db.add(row)
        for field in ("total_discovered", "new_found", "eligible_count", "rejected_count", "unknown_count",
                      "shortlisted_count", "prepared_count", "submitted_count", "pending_approvals_count",
                      "failed_count", "summary_markdown", "details_json"):
            setattr(row, field, getattr(resp, field))
        row.created_at = datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return ReportingService._response(day, d, row)

    @staticmethod
    def _row_response(r: DailyReport) -> DailyReportResponse:
        return DailyReportResponse(
            id=r.id, report_date=r.report_date, total_discovered=r.total_discovered or 0, new_found=r.new_found or 0,
            eligible_count=r.eligible_count or 0, rejected_count=r.rejected_count or 0, unknown_count=r.unknown_count or 0,
            shortlisted_count=r.shortlisted_count or 0, prepared_count=r.prepared_count or 0,
            submitted_count=r.submitted_count or 0, pending_approvals_count=r.pending_approvals_count or 0,
            failed_count=r.failed_count or 0, summary_markdown=r.summary_markdown or "",
            details_json=r.details_json or {}, created_at=r.created_at,
        )

    @staticmethod
    async def get_report_history(db: AsyncSession, limit: int = 30) -> List[DailyReportResponse]:
        rows = (await db.execute(select(DailyReport).order_by(desc(DailyReport.report_date)).limit(limit))).scalars().all()
        return [ReportingService._row_response(r) for r in rows]

    @staticmethod
    async def get_report_by_id(db: AsyncSession, report_id: str) -> DailyReportResponse:
        r = (await db.execute(select(DailyReport).where(DailyReport.id == report_id))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Report '{report_id}' not found.")
        return ReportingService._row_response(r)
