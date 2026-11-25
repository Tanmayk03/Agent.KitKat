"""
Stage 7 tests: timezone-correct daily reports (read-only GET, explicit save),
follow-ups due, scheduler daily/interval modes with persisted settings and run history.
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from backend.database.db import AsyncSessionLocal
from backend.database.models import Application, DailyReport, DiscoveryRun, Job
from backend.scheduler.daily_scheduler import daily_scheduler
from backend.services.halt import set_halted
from backend.services.profile_service import ProfileService
from backend.services.reporting_service import day_window_utc, today_local

pytestmark = pytest.mark.asyncio


async def add_job(fetched_at: datetime, **kw) -> str:
    jid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(Job(id=jid, company=kw.get("company", "Acme"), title=kw.get("title", "SDE Intern"),
                  url=f"https://x/{jid}", raw_text="Batch 2027", source="manual_text",
                  fetched_at=fetched_at, created_at=fetched_at))
        await s.commit()
    return jid


async def add_run(started: datetime, status="success", trigger="scheduled", failed_sources=0):
    async with AsyncSessionLocal() as s:
        s.add(DiscoveryRun(id=str(uuid.uuid4()), trigger=trigger, status=status, started_at=started,
                           finished_at=started + timedelta(minutes=1), total_fetched=10, new_saved=2,
                           failed_sources=failed_sources, error="boom" if status == "failed" else None))
        await s.commit()


def utc_inside(day: date, hours=1) -> datetime:
    start, _ = day_window_utc(day)
    return start + timedelta(hours=hours)


# --------------------------------------------------------------------------- timezone window
async def test_day_window_is_local_midnight_to_midnight():
    start, end = day_window_utc(date(2026, 11, 26))      # Asia/Kolkata = UTC+5:30
    assert start == datetime(2026, 11, 25, 18, 30)
    assert end == datetime(2026, 11, 26, 18, 30)


# --------------------------------------------------------------------------- report numbers
async def test_report_counts_only_that_local_day(client):
    day = today_local() - timedelta(days=1)
    start, end = day_window_utc(day)
    await add_job(start + timedelta(minutes=5))
    await add_job(end - timedelta(minutes=5))
    await add_job(start - timedelta(minutes=5))           # previous local day: excluded
    await add_job(end + timedelta(minutes=5))             # next local day: excluded
    await add_run(utc_inside(day), status="success")
    await add_run(utc_inside(day, 2), status="failed", trigger="manual")

    r = (await client.get("/api/reports/daily", params={"target_date": day.isoformat()})).json()
    a = r["details_json"]["activity"]
    assert a["new_jobs"] == 2 and r["new_found"] == 2
    assert a["discovery_runs"] == 2
    assert a["discovery_runs_failed"] == 1
    assert a["scheduled_runs"] == 1
    assert a["listings_fetched"] == 20
    assert r["details_json"]["day"] == day.isoformat()


async def test_empty_day_is_all_zero_not_invented(client):
    r = (await client.get("/api/reports/daily", params={"target_date": "2026-01-01"})).json()
    a = dict(r["details_json"]["activity"])
    assert set(a.pop("responses").values()) == {0}
    assert {k: v for k, v in a.items() if v} == {}
    assert r["details_json"]["top_new"] == []


async def test_get_is_read_only_and_generate_upserts(client):
    day = today_local().isoformat()
    await client.get("/api/reports/daily")
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(func.count()).select_from(DailyReport))).scalar_one() == 0

    r1 = await client.post("/api/reports/daily/generate")
    assert r1.status_code == 200
    await add_job(datetime.utcnow())
    r2 = (await client.post("/api/reports/daily/generate", params={"target_date": day})).json()
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(func.count()).select_from(DailyReport))).scalar_one() == 1
    assert r2["new_found"] == r1.json()["new_found"] + 1

    hist = (await client.get("/api/reports/history")).json()
    assert [h["report_date"] for h in hist] == [day]


async def test_bad_date_rejected(client):
    assert (await client.get("/api/reports/daily", params={"target_date": "26-11-2026"})).status_code in (400, 422)


# --------------------------------------------------------------------------- follow-ups
async def _app(job_id, stage, follow_up):
    async with AsyncSessionLocal() as s:
        a = Application(id=str(uuid.uuid4()), job_id=job_id, status=stage, stage=stage, follow_up_date=follow_up)
        s.add(a)
        await s.commit()
        return a.id


async def test_follow_ups_due_only_open_and_due(client):
    today = today_local()
    due = await _app(await add_job(datetime.utcnow(), company="DueCo"), "submitted", (today - timedelta(days=1)).isoformat())
    await _app(await add_job(datetime.utcnow()), "rejected", (today - timedelta(days=1)).isoformat())
    await _app(await add_job(datetime.utcnow()), "submitted", (today + timedelta(days=3)).isoformat())
    await _app(await add_job(datetime.utcnow()), "submitted", None)

    items = (await client.get("/api/applications/follow-ups")).json()
    assert [i["id"] for i in items] == [due]
    later = (await client.get("/api/applications/follow-ups",
                              params={"due_by": (today + timedelta(days=5)).isoformat()})).json()
    assert len(later) == 2

    rep = (await client.get("/api/reports/daily")).json()
    assert rep["details_json"]["snapshot"]["follow_ups_due"] == 1
    assert rep["details_json"]["follow_ups"][0]["company"] == "DueCo"


# --------------------------------------------------------------------------- scheduler
@pytest.fixture
async def scheduler_off():
    yield
    await daily_scheduler.disable()


async def _prefs():
    async with AsyncSessionLocal() as s:
        p = await ProfileService.get_or_create_profile(s)
        return dict(p.application_preferences or {})


async def test_scheduler_daily_mode(client, scheduler_off):
    r = (await client.post("/api/scheduler/start", params={"hour": 7, "minute": 15})).json()
    assert r["is_running"] and r["mode"] == "daily"
    assert r["description"] == "Every day at 07:15"
    assert r["next_run_time"]
    p = await _prefs()
    assert p["scheduler_enabled"] is True and p["schedule_mode"] == "daily" and p["daily_search_time"] == "07:15"


async def test_scheduler_interval_mode_persists_and_restores(client, scheduler_off):
    r = (await client.post("/api/scheduler/start", params={"mode": "interval", "interval_hours": 4})).json()
    assert r["mode"] == "interval" and r["interval_hours"] == 4
    assert r["description"] == "Every 4 hours"
    p = await _prefs()
    assert p["schedule_mode"] == "interval" and p["interval_hours"] == 4

    daily_scheduler.stop()
    daily_scheduler.start(9, 0)                     # wrong mode in memory…
    await daily_scheduler.restore_from_profile()     # …restored from saved prefs
    assert daily_scheduler.mode == "interval" and daily_scheduler.interval_hours == 4


async def test_scheduler_rejects_bad_interval(client, scheduler_off):
    r = await client.post("/api/scheduler/start", params={"mode": "interval", "interval_hours": 1})
    assert r.status_code == 422
    r = await client.post("/api/scheduler/start", params={"mode": "weekly"})
    assert r.status_code == 422


async def test_scheduler_refuses_to_start_while_halted(client, scheduler_off):
    async with AsyncSessionLocal() as s:
        await set_halted(s, True)
    try:
        r = await client.post("/api/scheduler/start")
        assert r.status_code == 423
        assert not daily_scheduler.is_running
    finally:
        async with AsyncSessionLocal() as s:
            await set_halted(s, False)


async def test_status_lists_recent_runs_and_failures(client):
    now = datetime.utcnow()
    await add_run(now - timedelta(days=1), status="failed")
    await add_run(now - timedelta(hours=1), status="success", failed_sources=1)
    await add_run(now - timedelta(days=10), status="failed")      # older than 7 days
    st = (await client.get("/api/scheduler/status")).json()
    assert len(st["recent_runs"]) == 3
    assert st["recent_runs"][0]["status"] == "success"          # newest first
    assert st["recent_runs"][0]["failed_sources"] == 1
    assert st["failed_runs_7d"] == 1
    assert st["timezone"] == "Asia/Kolkata"
