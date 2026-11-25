"""
Stage 3 tests: resilient fetching, pagination, career boards, expiry detection,
source-health history, background runs. All HTTP is mocked (httpx.MockTransport).
"""

import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import select

from backend.database.db import AsyncSessionLocal
from backend.database.models import DiscoveryRun, Job, SourceRun
from backend.tools import http_fetch, job_discovery_sources, career_boards
from backend.tools.http_fetch import SourceFetchError
from backend.tools.career_boards import (
    AshbyBoardSource, GreenhouseBoardSource, LeverBoardSource, parse_board_url,
)
from backend.tools.job_discovery_sources import (
    ArbeitnowDiscoverySource, BaseDiscoverySource, TechInternshipsDiscoverySource,
)

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------- helpers
@pytest.fixture
def sleeps(monkeypatch):
    waited = []

    async def fake_sleep(seconds):
        waited.append(seconds)
    monkeypatch.setattr(http_fetch, "sleep", fake_sleep)
    return waited


def mock_http(monkeypatch, handler):
    """Route every source HTTP client through `handler(request) -> httpx.Response`."""
    def factory(timeout: float = 20.0):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=timeout)
    monkeypatch.setattr(http_fetch, "make_client", factory)
    monkeypatch.setattr(job_discovery_sources, "make_client", factory)
    monkeypatch.setattr(career_boards, "make_client", factory)


async def add_job(**kw) -> str:
    data = dict(id=str(uuid.uuid4()), company="Acme", title="Software Engineer Intern",
                url=f"https://example.com/{uuid.uuid4()}", location="Bangalore, India", status="discovered")
    data.update(kw)
    async with AsyncSessionLocal() as s:
        s.add(Job(**data))
        await s.commit()
    return data["id"]


async def get_job(job_id: str) -> Job:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(Job).where(Job.id == job_id))).scalars().first()


# --------------------------------------------------------------------------- retries
async def test_fetch_retries_server_errors_then_succeeds(sleeps):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={"ok": True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        res = await http_fetch.fetch(c, "https://x.test/a")
    assert res.json() == {"ok": True} and len(calls) == 3 and len(sleeps) == 2


async def test_fetch_honours_retry_after_and_caps_it(sleeps):
    responses = [httpx.Response(429, headers={"Retry-After": "2"}),
                 httpx.Response(429, headers={"Retry-After": "999"}),
                 httpx.Response(200, json={})]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: responses.pop(0))) as c:
        await http_fetch.fetch(c, "https://x.test/a")
    assert sleeps == [2.0, http_fetch.MAX_RETRY_AFTER_SECONDS]


async def test_fetch_does_not_retry_client_errors(sleeps):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404))) as c:
        with pytest.raises(SourceFetchError) as e:
            await http_fetch.fetch(c, "https://x.test/missing")
    assert e.value.status_code == 404 and sleeps == []


async def test_fetch_gives_up_with_clear_error(sleeps):
    def boom(req):
        raise httpx.ConnectError("down", request=req)
    async with httpx.AsyncClient(transport=httpx.MockTransport(boom)) as c:
        with pytest.raises(SourceFetchError) as e:
            await http_fetch.fetch(c, "https://x.test/a", retries=2)
    assert "after 3 attempts" in str(e.value)


# --------------------------------------------------------------------------- pagination
async def test_arbeitnow_follows_pages(monkeypatch, sleeps):
    pages = {
        "1": {"data": [{"title": "Senior Engineer", "company_name": "A", "url": "https://a/1", "remote": True,
                        "description": "", "slug": "a1"}], "links": {"next": "x"}},
        "2": {"data": [{"title": "Software Engineer Intern", "company_name": "B", "url": "https://b/2",
                        "remote": True, "location": "", "description": "internship", "slug": "b2"}],
              "links": {"next": None}},
    }
    seen = []

    def handler(req):
        page = req.url.params.get("page")
        seen.append(page)
        return httpx.Response(200, json=pages[page])
    mock_http(monkeypatch, handler)
    res = await ArbeitnowDiscoverySource().search([], [], limit=5)
    assert seen == ["1", "2"] and [r["company"] for r in res] == ["B"]


# --------------------------------------------------------------------------- career boards
@pytest.mark.parametrize("url,expected", [
    ("https://boards.greenhouse.io/acme", ("greenhouse", "acme")),
    ("https://job-boards.greenhouse.io/acme/jobs/123", ("greenhouse", "acme")),
    ("boards.greenhouse.io/embed/job_board?for=acme", ("greenhouse", "acme")),
    ("https://jobs.lever.co/acme/abc-123", ("lever", "acme")),
    ("https://jobs.ashbyhq.com/acme", ("ashby", "acme")),
])
async def test_parse_board_url(url, expected):
    assert parse_board_url(url) == expected


@pytest.mark.parametrize("bad", ["https://example.com/careers", "https://jobs.lever.co/", "https://boards.greenhouse.io/../x"])
async def test_parse_board_url_rejects_unknown(bad):
    with pytest.raises(ValueError):
        parse_board_url(bad)


async def test_greenhouse_parse_filters_and_unescapes():
    src = GreenhouseBoardSource("acme", "Acme")
    ids, res = src.parse({"jobs": [
        {"id": 1, "title": "Software Engineer Intern", "absolute_url": "https://gh/1",
         "location": {"name": "Bengaluru, India"}, "content": "&lt;p&gt;Python &amp; React&lt;/p&gt;"},
        {"id": 2, "title": "Senior Software Engineer", "absolute_url": "https://gh/2", "location": {"name": "Remote"}},
        {"id": 3, "title": "Account Executive Intern", "absolute_url": "https://gh/3", "location": {"name": "India"}},
        {"id": 4, "title": "Software Engineer Intern", "absolute_url": "https://gh/4", "location": {"name": "Austin, TX"}},
    ]})
    assert ids == {"acme:1", "acme:2", "acme:3", "acme:4"}  # snapshot includes every open job
    assert [r["job_id_external"] for r in res] == ["acme:1"]
    assert "Python & React" in res[0]["description"] and res[0]["posted_at"] is None
    assert res[0]["company"] == "Acme" and res[0]["source"] == "greenhouse:acme"


async def test_lever_parse_uses_workplace_and_commitment():
    src = LeverBoardSource("acme", "Acme")
    _, res = src.parse([
        {"id": "x1", "text": "Backend Developer", "hostedUrl": "https://lv/x1", "workplaceType": "remote",
         "categories": {"location": "Remote - India", "commitment": "Internship"}, "descriptionPlain": "Go and Python"},
        {"id": "x2", "text": "Backend Developer", "hostedUrl": "https://lv/x2", "workplaceType": "on-site",
         "categories": {"location": "Berlin", "commitment": "Full-time"}, "descriptionPlain": "5+ years"},
    ])
    assert len(res) == 1 and res[0]["work_mode"] == "Remote" and res[0]["employment_type"] == "Internship"


async def test_ashby_parse_keeps_documented_dates_and_compensation():
    src = AshbyBoardSource("acme", "Acme")
    _, res = src.parse({"jobs": [
        {"id": "u1", "title": "Software Engineer", "jobUrl": "https://ash/u1", "location": "Hyderabad, India",
         "workplaceType": "Hybrid", "employmentType": "Intern", "publishedAt": "2026-11-20T10:00:00Z",
         "descriptionPlain": "Build APIs", "compensation": {"compensationTierSummary": "₹50K – ₹70K per month"}},
        {"id": "u2", "title": "Software Engineer Intern", "jobUrl": "https://ash/u2", "isListed": False},
    ]})
    assert len(res) == 1
    assert res[0]["posted_at"].startswith("2026-11-20") and res[0]["salary_stipend"] == "₹50K – ₹70K per month"


async def test_lever_partial_snapshot_is_not_used_for_expiry(monkeypatch, sleeps):
    monkeypatch.setattr(LeverBoardSource, "MAX_PAGES", 1)
    monkeypatch.setattr(LeverBoardSource, "PAGE", 1)
    mock_http(monkeypatch, lambda r: httpx.Response(200, json=[{"id": "a", "text": "Intern", "hostedUrl": "https://l/a"}]))
    src = LeverBoardSource("acme")
    await src.search([], [], limit=5)
    assert src.snapshot_ids is None  # more pages may exist: no expiry evidence


# --------------------------------------------------------------------------- expiry + history
class FakeSource(BaseDiscoverySource):
    def __init__(self, name, items=None, error=None, expired=None, snapshot=None):
        super().__init__()
        self.name, self.items, self.error = name, items or [], error
        self._expired, self._snapshot = expired, snapshot
        self.description = f"fake {name}"

    async def search(self, *a, **k):
        if self.error:
            raise SourceFetchError(self.error, 503)
        if self._expired:
            self.expired_external_ids = set(self._expired)
        if self._snapshot is not None:
            self.snapshot_scope, self.snapshot_ids = self._snapshot
        return [dict(i) for i in self.items]


def item(n, source="good", **kw):
    d = dict(title="Software Engineer Intern", company=f"Co{n}", url=f"https://jobs.example/{n}",
             location="Bangalore, India", work_mode="Onsite", source=source, job_id_external=str(n),
             raw_text="Software Engineer Intern")
    d.update(kw)
    return d


async def run(monkeypatch, sources):
    from backend.services import discovery_service as ds
    monkeypatch.setattr(ds, "DISCOVERY_SOURCES", sources)
    async with AsyncSessionLocal() as s:
        return await ds.DiscoveryService.run_discovery(s, auto_prepare_applications=False)


async def test_closed_flag_and_board_snapshot_mark_jobs_expired(monkeypatch):
    closed = await add_job(source="feed", job_id_external="7")
    gone = await add_job(source="greenhouse:acme", job_id_external="acme:2", company="Acme2")
    still = await add_job(source="greenhouse:acme", job_id_external="acme:1", company="Acme1")
    applied = await add_job(source="greenhouse:acme", job_id_external="acme:3", company="Acme3", status="applied")
    res = await run(monkeypatch, [
        FakeSource("feed", expired=["7"]),
        FakeSource("greenhouse:acme", snapshot=("acme:", {"acme:1"})),
    ])
    assert res.expired_marked == 3
    assert (await get_job(closed)).status == "expired"
    g = await get_job(gone)
    assert g.status == "expired" and "No longer listed" in g.expiry_evidence
    assert (await get_job(still)).expired_at is None
    a = await get_job(applied)
    assert a.status == "applied" and a.expired_at is not None  # history kept, closure recorded


async def test_simplify_inactive_ids_are_reported():
    src = TechInternshipsDiscoverySource()
    src.reset_run_state()
    src.parse([{"id": "old", "active": False, "title": "x", "company_name": "y", "url": "z"}], True)
    assert src.expired_external_ids == {"old"}


async def test_duplicates_refresh_last_seen_and_dedupe_by_city(monkeypatch):
    first = await run(monkeypatch, [FakeSource("good", items=[item(1)])])
    assert first.new_saved == 1
    async with AsyncSessionLocal() as s:
        job = (await s.execute(select(Job))).scalars().first()
        seen_before = job.last_seen_at
    await asyncio.sleep(0.01)
    second = await run(monkeypatch, [FakeSource("good", items=[
        item(1),                                                     # same source id -> duplicate
        item(2, company="Co1", url="https://other/2", job_id_external="x"),        # same co/title/city -> duplicate
        item(3, company="Co1", url="https://other/3", job_id_external="y", location="Pune, India"),  # other city -> new
    ])])
    assert second.duplicates_skipped == 2 and second.new_saved == 1
    async with AsyncSessionLocal() as s:
        job = (await s.execute(select(Job).where(Job.job_id_external == "1"))).scalars().first()
    assert job.last_seen_at > seen_before


async def test_run_history_and_source_health(monkeypatch, client):
    await run(monkeypatch, [FakeSource("good", items=[item(1)]), FakeSource("bad", error="HTTP 503")])
    async with AsyncSessionLocal() as s:
        runs = (await s.execute(select(DiscoveryRun))).scalars().all()
        srows = (await s.execute(select(SourceRun))).scalars().all()
    assert len(runs) == 1 and runs[0].status == "partial" and runs[0].progress == "Done"
    assert {r.source_name: r.ok for r in srows} == {"good": True, "bad": False}
    assert next(r for r in srows if r.source_name == "bad").http_status == 503

    health = {h["source_name"]: h for h in (await client.get("/api/discovery/health")).json()}
    assert health["bad"]["last_status"] == "failed" and "503" in health["bad"]["last_error"]
    assert health["good"]["last_status"] == "ok" and health["good"]["jobs_total"] == 1
    assert health["good"]["new_last_24h"] == 1 and health["good"]["success_rate"] == 1.0

    history = (await client.get("/api/discovery/runs")).json()
    assert history[0]["status"] == "partial" and len(history[0]["source_results"]) == 2


async def test_all_sources_failing_marks_run_failed(monkeypatch):
    res = await run(monkeypatch, [FakeSource("a", error="down"), FakeSource("b", error="down")])
    async with AsyncSessionLocal() as s:
        r = (await s.execute(select(DiscoveryRun).where(DiscoveryRun.id == res.run_id))).scalars().first()
    assert r.status == "failed" and res.failed_sources == 2


async def test_background_run_reports_progress_and_blocks_overlap(monkeypatch, client):
    from backend.services import discovery_service as ds
    gate = asyncio.Event()

    class Slow(FakeSource):
        async def search(self, *a, **k):
            await gate.wait()
            return [item(9)]
    monkeypatch.setattr(ds, "DISCOVERY_SOURCES", [Slow("slow")])

    r = await client.post("/api/discovery/runs", json={"auto_prepare_applications": False})
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    await asyncio.sleep(0.05)
    assert (await client.post("/api/discovery/runs", json={})).status_code == 409
    status = (await client.get(f"/api/discovery/runs/{run_id}")).json()
    assert status["status"] == "running" and "slow" in status["progress"]

    gate.set()
    for _ in range(100):
        status = (await client.get(f"/api/discovery/runs/{run_id}")).json()
        if status["status"] != "running":
            break
        await asyncio.sleep(0.05)
    assert status["status"] == "success" and status["new_saved"] == 1


async def test_interrupted_runs_are_marked_failed_on_startup():
    from backend.services.discovery_service import DiscoveryService
    async with AsyncSessionLocal() as s:
        run_id = await DiscoveryService.create_run_record(s, "manual")
        await DiscoveryService.mark_interrupted_runs(s)
        r = (await s.execute(select(DiscoveryRun).where(DiscoveryRun.id == run_id))).scalars().first()
    assert r.status == "failed" and "Interrupted" in r.error


# --------------------------------------------------------------------------- boards API
async def test_career_board_management_api(client):
    r = await client.post("/api/discovery/boards", json={"url": "https://jobs.lever.co/acme", "company": "Acme"})
    assert r.status_code == 200 and r.json() == [{"ats": "lever", "token": "acme", "company": "Acme", "enabled": True}]
    assert (await client.post("/api/discovery/boards", json={"url": "https://jobs.lever.co/acme"})).status_code == 409
    assert (await client.post("/api/discovery/boards", json={"url": "https://example.com/careers"})).status_code == 400
    names = [s["source_name"] for s in (await client.get("/api/discovery/sources")).json()]
    assert "lever:acme" in names
    # saving the profile's preferences must not drop followed boards
    await client.put("/api/profile", json={"application_preferences": {"min_match_score": 70}})
    assert len((await client.get("/api/discovery/boards")).json()) == 1
    assert (await client.delete("/api/discovery/boards/lever/acme")).json() == []


async def test_stale_settings_save_cannot_drop_followed_boards(client):
    await client.post("/api/discovery/boards", json={"url": "https://jobs.ashbyhq.com/acme"})
    await client.put("/api/profile", json={"application_preferences": {"career_boards": [], "min_match_score": 60}})
    assert len((await client.get("/api/discovery/boards")).json()) == 1
