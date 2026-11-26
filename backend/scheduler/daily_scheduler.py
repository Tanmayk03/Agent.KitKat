"""
Agent KitKat - Daily Autonomous Job Hunting Scheduler
Coordinates daily scheduled discovery cycles using APScheduler.

Guarantees:
- The enabled/disabled state and run time are persisted in the profile's
  application_preferences ("scheduler_enabled", "daily_search_time") and restored at startup.
- Only one discovery cycle can run at a time (cron and "run now" share one lock).
- The scheduler never submits applications; it only discovers, evaluates and drafts.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.config import get_settings

from backend.database.db import AsyncSessionLocal
from backend.services.discovery_service import DiscoveryService
from backend.services.reporting_service import ReportingService
from backend.services.profile_service import ProfileService

logger = logging.getLogger("agent_kitkat.scheduler")

JOB_ID = "daily_job_hunt"
ALLOWED_INTERVAL_HOURS = (3, 4, 6, 8, 12, 24)


class SchedulerBusyError(RuntimeError):
    """Raised when a discovery cycle is already running."""


class DailyScheduler:
    """Manages automated background recurring job discovery runs."""

    _background_tasks: set = set()

    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._enabled = False
        self._scheduled_time = "09:00"
        self._mode = "daily"          # daily | interval
        self._interval_hours = 6
        self._run_lock = asyncio.Lock()
        self.last_run_started_at: Optional[datetime] = None
        self.last_run_finished_at: Optional[datetime] = None
        self.last_run_status: Optional[str] = None
        self.last_run_error: Optional[str] = None

    # ------------------------------------------------------------------ state
    @property
    def is_running(self) -> bool:
        """True when the recurring schedule is enabled (not whether a cycle is executing)."""
        return self._enabled and self._scheduler is not None and self._scheduler.running

    @property
    def run_lock(self) -> asyncio.Lock:
        """Shared lock: manual discovery and scheduled cycles never overlap."""
        return self._run_lock

    @property
    def cycle_in_progress(self) -> bool:
        return self._run_lock.locked()

    def get_scheduled_time(self) -> str:
        return self._scheduled_time

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def interval_hours(self) -> int:
        return self._interval_hours

    def describe(self) -> str:
        if self._mode == "interval":
            return f"Every {self._interval_hours} hours"
        return f"Every day at {self._scheduled_time}"

    def get_next_run_time(self) -> Optional[str]:
        if not self.is_running:
            return None
        job = self._scheduler.get_job(JOB_ID)
        if job and job.next_run_time:
            from backend.services.reporting_service import local_tz
            return job.next_run_time.astimezone(local_tz()).strftime("%Y-%m-%d %H:%M %Z")
        return None

    # ---------------------------------------------------------------- control
    def _ensure_scheduler(self) -> AsyncIOScheduler:
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler(timezone=get_settings().TIMEZONE, job_defaults={"max_instances": 1, "coalesce": True, "misfire_grace_time": 3600})
        if not self._scheduler.running:
            self._scheduler.start()
        return self._scheduler

    def start(self, hour: int = 9, minute: int = 0) -> None:
        """Enable (or reconfigure) a daily schedule in your timezone. Does not persist; see enable()."""
        sched = self._ensure_scheduler()
        self._mode = "daily"
        self._scheduled_time = f"{hour:02d}:{minute:02d}"
        sched.add_job(
            self._scheduled_cycle,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=get_settings().TIMEZONE),
            id=JOB_ID,
            name="Autonomous Daily Career Hunt",
            replace_existing=True,
        )
        self._enabled = True
        logger.info("⏰ Job discovery scheduled: %s", self.describe())

    def start_interval(self, hours: int) -> None:
        """Enable (or reconfigure) an every-N-hours schedule. Does not persist; see enable()."""
        if hours not in ALLOWED_INTERVAL_HOURS:
            raise ValueError(f"Interval must be one of {ALLOWED_INTERVAL_HOURS} hours.")
        sched = self._ensure_scheduler()
        self._mode = "interval"
        self._interval_hours = hours
        sched.add_job(
            self._scheduled_cycle,
            trigger=IntervalTrigger(hours=hours),
            id=JOB_ID,
            name="Autonomous Career Hunt (interval)",
            replace_existing=True,
        )
        self._enabled = True
        logger.info("⏰ Job discovery scheduled: %s", self.describe())

    def start_from_prefs(self, prefs: dict) -> None:
        """Re-create the saved schedule (used at startup and on Resume)."""
        if prefs.get("schedule_mode") == "interval":
            try:
                self.start_interval(int(prefs.get("interval_hours") or 6))
                return
            except ValueError:
                pass
        try:
            hour, minute = (int(x) for x in str(prefs.get("daily_search_time") or "09:00").split(":", 1))
        except ValueError:
            hour, minute = 9, 0
        self.start(hour, minute)

    def stop(self) -> None:
        """Pause the recurring schedule (the scheduler object stays alive)."""
        if self._scheduler and self._scheduler.get_job(JOB_ID):
            self._scheduler.remove_job(JOB_ID)
        self._enabled = False
        logger.info("🛑 Daily job hunting schedule paused.")

    def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self._scheduler = None
        self._enabled = False

    async def enable(self, hour: int = 9, minute: int = 0, mode: str = "daily", interval_hours: Optional[int] = None) -> None:
        """Start and persist."""
        if mode == "interval":
            self.start_interval(int(interval_hours or 6))
        else:
            self.start(hour, minute)
        await self._persist(enabled=True)

    async def disable(self) -> None:
        """Pause and persist."""
        self.stop()
        await self._persist(enabled=False)

    async def _persist(self, enabled: bool) -> None:
        async with AsyncSessionLocal() as session:
            profile = await ProfileService.get_or_create_profile(session)
            prefs = dict(profile.application_preferences or {})
            prefs["scheduler_enabled"] = enabled
            prefs["daily_search_time"] = self._scheduled_time
            prefs["schedule_mode"] = self._mode
            prefs["interval_hours"] = self._interval_hours
            profile.application_preferences = prefs
            await session.commit()

    async def restore_from_profile(self) -> None:
        """Called at app startup: re-enable the schedule if the user had enabled it."""
        async with AsyncSessionLocal() as session:
            await DiscoveryService.mark_interrupted_runs(session)
            profile = await ProfileService.get_or_create_profile(session)
            prefs = profile.application_preferences or {}
        self._scheduled_time = str(prefs.get("daily_search_time") or "09:00")
        self._mode = prefs.get("schedule_mode") or "daily"
        self._interval_hours = int(prefs.get("interval_hours") or 6)
        if prefs.get("automation_halted"):
            logger.warning("Automation is halted by Emergency Stop; the schedule stays paused until you Resume.")
        elif prefs.get("scheduler_enabled"):
            self.start_from_prefs(prefs)
            logger.info("Restored schedule (%s).", self.describe())

    # -------------------------------------------------------------- execution
    async def trigger_now(self) -> dict:
        """Run one cycle immediately. Raises SchedulerBusyError if a cycle is already running."""
        if self._run_lock.locked():
            raise SchedulerBusyError("A discovery cycle is already running.")
        from backend.services.halt import ensure_not_halted
        async with AsyncSessionLocal() as session:
            await ensure_not_halted(session)
        logger.info("⚡ Immediate on-demand job discovery cycle requested.")
        return await self._run_daily_cycle()

    async def _scheduled_cycle(self) -> None:
        if self._run_lock.locked():
            logger.warning("Skipping scheduled cycle: previous cycle still running.")
            return
        await self._run_daily_cycle()

    async def _run_daily_cycle(self) -> dict:
        """Discovery + evaluation + drafting + daily report. Never submits anything."""
        async with self._run_lock:
            self.last_run_started_at = datetime.utcnow()
            self.last_run_error = None
            logger.info("🚀 Executing autonomous career hunt cycle...")
            try:
                async with AsyncSessionLocal() as session:
                    discovery_result = await DiscoveryService.run_discovery(
                        db=session,
                        auto_evaluate=True,
                        auto_prepare_applications=True,
                        trigger="scheduled",
                    )
                    report = await ReportingService.generate_daily_report(session)
                self.last_run_status = "success"
                logger.info("✅ Cycle complete. Report ID: %s", report.id[:8])
                # Daily automatic backup (keeps the last 7); a failure here never fails the cycle.
                try:
                    import asyncio
                    from backend.maintenance import backup
                    await asyncio.to_thread(backup.auto_backup_if_due)
                except Exception as be:
                    logger.error("Automatic backup after the scheduled run failed: %s", be)
                return {
                    "status": "success",
                    "discovery": discovery_result.model_dump(),
                    "report_id": report.id,
                }
            except Exception as e:
                self.last_run_status = "error"
                self.last_run_error = str(e)
                logger.exception("❌ Error executing discovery cycle")
                return {"status": "error", "error": str(e)}
            finally:
                self.last_run_finished_at = datetime.utcnow()


    async def start_background_discovery(self, **kwargs) -> str:
        """
        Start a discovery run in the background and return its run_id immediately.
        The dashboard polls GET /api/discovery/runs/{run_id} for progress.
        Raises SchedulerBusyError if another cycle is running.
        """
        if self._run_lock.locked():
            raise SchedulerBusyError("A discovery cycle is already running.")
        from backend.services.halt import ensure_not_halted
        async with AsyncSessionLocal() as session:
            await ensure_not_halted(session)
        await self._run_lock.acquire()  # held until the task finishes
        try:
            async with AsyncSessionLocal() as session:
                run_id = await DiscoveryService.create_run_record(session, "background")
        except Exception:
            self._run_lock.release()
            raise

        async def _worker():
            self.last_run_started_at = datetime.utcnow()
            try:
                async with AsyncSessionLocal() as session:
                    await DiscoveryService.run_discovery(db=session, run_id=run_id, **kwargs)
                    await ReportingService.generate_daily_report(session)
                self.last_run_status = "success"
            except Exception as e:
                self.last_run_status, self.last_run_error = "error", str(e)
                logger.exception("Background discovery run %s failed", run_id)
            finally:
                self.last_run_finished_at = datetime.utcnow()
                self._run_lock.release()

        task = asyncio.create_task(_worker())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return run_id


# Singleton instance
daily_scheduler = DailyScheduler()
