"""
Agent KitKat - Real Job Harvest & Database Refresh Script
Purges any old or test entries and executes a 100% real live discovery sweep
across Arbeitnow, WeWorkRemotely, Remotive, and Jobicy for genuine software, AI, and developer roles.
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
import logging
import sqlite3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("agent_kitkat.harvest_real")


def reset_and_clean_jobs():
    conn = sqlite3.connect("storage/agent_kitkat.db")
    cursor = conn.cursor()

    logger.info("Purging non-profile job records for fresh real harvest...")
    cursor.execute("DELETE FROM applications")
    cursor.execute("DELETE FROM approval_requests")
    cursor.execute("DELETE FROM application_drafts")
    cursor.execute("DELETE FROM match_results")
    cursor.execute("DELETE FROM eligibility_results")
    cursor.execute("DELETE FROM jobs")
    cursor.execute("DELETE FROM daily_reports")

    conn.commit()
    conn.close()
    logger.info("Database reset. Ground-truth candidate profile and active resume remain untouched.")


async def run_real_discovery():
    from backend.database.db import AsyncSessionLocal
    from backend.services.discovery_service import DiscoveryService
    from backend.services.reporting_service import ReportingService

    logger.info("Starting 100% REAL LIVE discovery sweep across Arbeitnow, WeWorkRemotely, Remotive, and Jobicy...")
    async with AsyncSessionLocal() as session:
        result = await DiscoveryService.run_discovery(
            db=session,
            keywords=["developer", "software", "python", "react", "data", "engineer", "full stack"],
            locations=["Remote", "India"],
            limit_per_source=4,
            auto_evaluate=True,
            auto_prepare_applications=True
        )

        logger.info(
            "Discovery Completed: Discovered=%d, New Saved=%d, Duplicates Skipped=%d, Eligible=%d, Shortlisted=%d",
            result.total_discovered, result.new_saved, result.duplicates_skipped, result.eligible_count, result.shortlisted_count
        )

        # Generate real daily audit report
        report = await ReportingService.generate_daily_report(session)
        logger.info("Real Daily Report Generated: Date=%s, Total Discovered=%d, Eligible=%d, Prepared=%d",
                    report.report_date, report.total_discovered, report.eligible_count, report.prepared_count)


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
    reset_and_clean_jobs()
    asyncio.run(run_real_discovery())
