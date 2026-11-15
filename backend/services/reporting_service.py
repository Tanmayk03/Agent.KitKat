"""
Agent KitKat - Daily Reporting Service
Synthesizes real-time and historical daily activity reports strictly using
persisted database records. Zero fake statistics or fabricated data.
"""

import uuid
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from backend.database.models import (
    Job,
    EligibilityResult,
    MatchResult,
    ApplicationDraft,
    ApprovalRequest,
    Application,
    DailyReport
)
from backend.schemas.reporting import DailyReportResponse

logger = logging.getLogger("agent_kitkat.reporting_service")


class ReportingService:
    """
    Generates deterministic reports using real database metrics.
    """

    @staticmethod
    async def generate_daily_report(db: AsyncSession, target_date: Optional[str] = None) -> DailyReportResponse:
        """
        Aggregate database records for target date (default: today) and generate a markdown summary.
        """
        today_str = target_date or datetime.utcnow().strftime("%Y-%m-%d")

        # 1. Query Real Metrics from Database
        # Total discovered jobs
        total_jobs_res = await db.execute(select(func.count(Job.id)))
        total_discovered = total_jobs_res.scalar_one() or 0

        # Jobs discovered on target date
        all_jobs_res = await db.execute(select(Job))
        jobs = all_jobs_res.scalars().all()
        new_found = sum(1 for j in jobs if j.created_at and j.created_at.strftime("%Y-%m-%d") == today_str)

        # Eligibility metrics
        elig_res = await db.execute(select(EligibilityResult))
        elig_list = elig_res.scalars().all()
        eligible_count = sum(1 for e in elig_list if e.overall_status == "PASS")
        rejected_count = sum(1 for e in elig_list if e.overall_status == "FAIL")
        unknown_count = sum(1 for e in elig_list if e.overall_status == "UNKNOWN")

        # Match metrics (shortlisted: score >= 75%)
        match_res = await db.execute(select(MatchResult))
        match_list = match_res.scalars().all()
        shortlisted_count = sum(1 for m in match_list if m.overall_score >= 75.0)

        # Application Drafts prepared
        draft_res = await db.execute(select(ApplicationDraft))
        drafts = draft_res.scalars().all()
        prepared_count = len(drafts)

        # Pending approvals
        appr_res = await db.execute(select(ApprovalRequest).where(ApprovalRequest.status == "pending"))
        pending_approvals = appr_res.scalars().all()
        pending_approvals_count = len(pending_approvals)

        # Applications submitted & failed
        apps_res = await db.execute(select(Application))
        apps = apps_res.scalars().all()
        submitted_count = sum(1 for a in apps if a.status == "submitted")
        failed_count = sum(1 for a in apps if a.status in ["submission_failed", "failed"])

        # 2. Build Formatted Markdown Summary
        summary_md = f"""# 🍫 Agent KitKat - Daily Activity Report
**Report Date:** {today_str}
**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

---

### 📊 Executive Summary
| Metric | Value |
|---|---:|
| **Total Jobs Discovered** | **{total_discovered}** |
| **New Opportunities Found Today** | **{new_found}** |
| **Eligible Opportunities (PASS)** | **{eligible_count}** |
| **Ineligible Opportunities (FAIL)** | **{rejected_count}** |
| **Needs Verification (UNKNOWN)** | **{unknown_count}** |
| **Shortlisted (Match ≥ 75%)** | **{shortlisted_count}** |
| **Applications Prepared** | **{prepared_count}** |
| **Applications Submitted** | **{submitted_count}** |
| **Pending Human Approvals** | **{pending_approvals_count}** |
| **Failed Applications** | **{failed_count}** |

---

### 🎯 Key Insights
- **Pipeline Health:** {eligible_count} out of {total_discovered} opportunities meet 100% of candidate profile qualifications.
- **Action Required:** {pending_approvals_count} application(s) awaiting your manual approval before submission.
- **Automation Status:** {submitted_count} application(s) successfully verified and delivered to hiring platforms.
"""

        details_json = {
            "total_discovered": total_discovered,
            "new_found": new_found,
            "eligible_count": eligible_count,
            "rejected_count": rejected_count,
            "unknown_count": unknown_count,
            "shortlisted_count": shortlisted_count,
            "prepared_count": prepared_count,
            "submitted_count": submitted_count,
            "pending_approvals_count": pending_approvals_count,
            "failed_count": failed_count,
        }

        # 3. Check for existing report on this date or create new
        rep_stmt = select(DailyReport).where(DailyReport.report_date == today_str)
        rep_res = await db.execute(rep_stmt)
        existing_report = rep_res.scalar_one_or_none()

        if existing_report:
            existing_report.total_discovered = total_discovered
            existing_report.new_found = new_found
            existing_report.eligible_count = eligible_count
            existing_report.rejected_count = rejected_count
            existing_report.unknown_count = unknown_count
            existing_report.shortlisted_count = shortlisted_count
            existing_report.prepared_count = prepared_count
            existing_report.submitted_count = submitted_count
            existing_report.pending_approvals_count = pending_approvals_count
            existing_report.failed_count = failed_count
            existing_report.summary_markdown = summary_md
            existing_report.details_json = details_json
            report_obj = existing_report
        else:
            report_obj = DailyReport(
                id=str(uuid.uuid4()),
                report_date=today_str,
                total_discovered=total_discovered,
                new_found=new_found,
                eligible_count=eligible_count,
                rejected_count=rejected_count,
                unknown_count=unknown_count,
                shortlisted_count=shortlisted_count,
                prepared_count=prepared_count,
                submitted_count=submitted_count,
                pending_approvals_count=pending_approvals_count,
                failed_count=failed_count,
                summary_markdown=summary_md,
                details_json=details_json
            )
            db.add(report_obj)

        await db.commit()
        await db.refresh(report_obj)

        return DailyReportResponse(
            id=report_obj.id,
            report_date=report_obj.report_date,
            total_discovered=report_obj.total_discovered,
            new_found=report_obj.new_found,
            eligible_count=report_obj.eligible_count,
            rejected_count=report_obj.rejected_count,
            unknown_count=report_obj.unknown_count,
            shortlisted_count=report_obj.shortlisted_count,
            prepared_count=report_obj.prepared_count,
            submitted_count=report_obj.submitted_count,
            pending_approvals_count=report_obj.pending_approvals_count,
            failed_count=report_obj.failed_count,
            summary_markdown=report_obj.summary_markdown,
            details_json=report_obj.details_json,
            created_at=report_obj.created_at
        )

    @staticmethod
    async def get_report_history(db: AsyncSession, limit: int = 30) -> List[DailyReportResponse]:
        """Fetch past daily reports sorted by date descending."""
        stmt = select(DailyReport).order_by(desc(DailyReport.report_date)).limit(limit)
        res = await db.execute(stmt)
        reports = res.scalars().all()

        return [
            DailyReportResponse(
                id=r.id,
                report_date=r.report_date,
                total_discovered=r.total_discovered,
                new_found=r.new_found,
                eligible_count=r.eligible_count,
                rejected_count=r.rejected_count,
                unknown_count=r.unknown_count,
                shortlisted_count=r.shortlisted_count,
                prepared_count=r.prepared_count,
                submitted_count=r.submitted_count,
                pending_approvals_count=r.pending_approvals_count,
                failed_count=r.failed_count,
                summary_markdown=r.summary_markdown,
                details_json=r.details_json,
                created_at=r.created_at
            )
            for r in reports
        ]

    @staticmethod
    async def get_report_by_id(db: AsyncSession, report_id: str) -> DailyReportResponse:
        """Fetch a specific daily report by ID."""
        stmt = select(DailyReport).where(DailyReport.id == report_id)
        res = await db.execute(stmt)
        r = res.scalar_one_or_none()

        if not r:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Daily report with ID '{report_id}' not found."
            )

        return DailyReportResponse(
            id=r.id,
            report_date=r.report_date,
            total_discovered=r.total_discovered,
            new_found=r.new_found,
            eligible_count=r.eligible_count,
            rejected_count=r.rejected_count,
            unknown_count=r.unknown_count,
            shortlisted_count=r.shortlisted_count,
            prepared_count=r.prepared_count,
            submitted_count=r.submitted_count,
            pending_approvals_count=r.pending_approvals_count,
            failed_count=r.failed_count,
            summary_markdown=r.summary_markdown,
            details_json=r.details_json,
            created_at=r.created_at
        )
