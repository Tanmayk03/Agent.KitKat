"""
Agent KitKat - Daily Autonomous Job Hunting Scheduler
Coordinates daily scheduled discovery cycles using APScheduler.
Triggers multi-source discovery, eligibility evaluation, application drafting,
and automated daily activity report generation.
"""

import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.database.db import AsyncSessionLocal
from backend.services.discovery_service import DiscoveryService
from backend.services.reporting_service import ReportingService
from backend.services.profile_service import ProfileService

logger = logging.getLogger("agent_kitkat.scheduler")


class DailyScheduler:
    """
    Manages automated background recurring job discovery runs.
    """

    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._is_running = False
        self._scheduled_time = "09:00"  # Default 9:00 AM daily

    @property
    def is_running(self) -> bool:
        return self._is_running and self._scheduler is not None and self._scheduler.running

    def get_scheduled_time(self) -> str:
        return self._scheduled_time

    def get_next_run_time(self) -> Optional[str]:
        if not self.is_running or not self._scheduler:
            return None
        job = self._scheduler.get_job("daily_job_hunt")
        if job and job.next_run_time:
            return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        return None

    def start(self, hour: int = 9, minute: int = 0) -> None:
        """Start or reconfigure the daily job hunting schedule."""
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler()

        self._scheduled_time = f"{hour:02d}:{minute:02d}"

        # Remove existing job if any
        if self._scheduler.get_job("daily_job_hunt"):
            self._scheduler.remove_job("daily_job_hunt")

        trigger = CronTrigger(hour=hour, minute=minute)
        self._scheduler.add_job(
            self._run_daily_cycle,
            trigger=trigger,
            id="daily_job_hunt",
            name="Autonomous Daily Career Hunt",
            replace_existing=True
        )

        if not self._scheduler.running:
            self._scheduler.start()

        self._is_running = True
        logger.info("⏰ Daily Job Hunting Scheduler active. Scheduled every day at %s", self._scheduled_time)

    def stop(self) -> None:
        """Pause or shut down the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

        self._is_running = False
        logger.info("🛑 Daily Job Hunting Scheduler stopped.")

    async def trigger_now(self) -> dict:
        """Trigger an immediate execution of the daily cycle in the background."""
        logger.info("⚡ Immediate on-demand job discovery cycle requested.")
        return await self._run_daily_cycle()

    async def _run_daily_cycle(self) -> dict:
        """Internal worker executing full discovery + reporting workflow."""
        logger.info("🚀 Executing autonomous daily career hunt cycle...")
        async with AsyncSessionLocal() as session:
            try:
                # 1. Run Autonomous Multi-Source Discovery
                discovery_result = await DiscoveryService.run_discovery(
                    db=session,
                    auto_evaluate=True,
                    auto_prepare_applications=True
                )

                # 2. Generate Real Daily Activity Report
                report = await ReportingService.generate_daily_report(session)

                logger.info("✅ Daily cycle complete. Generated report ID: %s", report.id[:8])
                return {
                    "status": "success",
                    "discovery": discovery_result.model_dump(),
                    "report_id": report.id
                }
            except Exception as e:
                logger.error("❌ Error executing daily cycle: %s", e)
                return {"status": "error", "error": str(e)}


# Singleton instance
daily_scheduler = DailyScheduler()
