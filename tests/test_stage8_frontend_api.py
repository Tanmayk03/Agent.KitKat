"""
Stage 8 tests: the Opportunities API (eligibility/score join, facets, filters, sort, pagination,
tracking state) and the PWA files served by the backend.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from backend.database.db import AsyncSessionLocal
from backend.database.models import Application, EligibilityResult, Job, MatchResult

pytestmark = pytest.mark.asyncio


async def job(title, el=None, score=None, *, company="Acme", work_mode="Onsite", location="Pune, India",
              status="analyzed", age_h=0, details=None, reasons=None, tracked_stage=None):
    jid = str(uuid.uuid4())
    t = datetime.utcnow() - timedelta(hours=age_h)
    async with AsyncSessionLocal() as s:
        s.add(Job(id=jid, title=title, company=company, work_mode=work_mode, location=location, status=status,
                  url=f"https://x/{jid}", source="manual_text", raw_text="x", fetched_at=t, created_at=t))
        if el:
            s.add(EligibilityResult(id=str(uuid.uuid4()), job_id=jid, overall_status=el,
                                    rejection_reasons=reasons if el == "FAIL" else [],
                                    unverified_requirements=reasons if el == "UNKNOWN" else []))
        if score is not None:
            s.add(MatchResult(id=str(uuid.uuid4()), job_id=jid, overall_score=score, recommendation="Apply",
                              matching_skills=["Python"], missing_skills=["Go"],
                              details_json=details or {"next_action": "Prepare an application draft and review it."}))
        if tracked_stage:
            s.add(Application(id=str(uuid.uuid4()), job_id=jid, status=tracked_stage, stage=tracked_stage))
        await s.commit()
    return jid


async def get(client, **params):
    r = await client.get("/api/jobs/opportunities", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_default_order_eligible_first_then_score(client):
    fail_hi = await job("Fail high", "FAIL", 95, reasons=["Requires 2025 graduates"])
    pass_lo = await job("Pass low", "PASS", 60)
    pass_hi = await job("Pass high", "PASS", 88)
    unk = await job("Unknown", "UNKNOWN", 90, reasons=["CGPA cutoff not stated"])
    none = await job("Not evaluated")
    d = await get(client)
    assert [i["id"] for i in d["items"]] == [pass_hi, pass_lo, unk, none, fail_hi]
    first = d["items"][0]
    assert first["match_score"] == 88 and first["eligibility_status"] == "PASS"
    assert first["above_threshold"] is True and d["items"][1]["above_threshold"] is False
    assert first["next_action"].startswith("Prepare")
    assert d["items"][2]["eligibility_reasons"] == ["CGPA cutoff not stated"]
    assert d["items"][4]["eligibility_reasons"] == ["Requires 2025 graduates"]
    assert d["items"][3]["eligibility_status"] is None and d["items"][3]["match_score"] is None


async def test_facets_and_eligibility_filter(client):
    await job("a", "PASS", 80); await job("b", "PASS", 70); await job("c", "FAIL", 50); await job("d")
    d = await get(client, eligibility="PASS")
    assert d["total"] == 2 and {i["eligibility_status"] for i in d["items"]} == {"PASS"}
    assert d["facets"] == {"PASS": 2, "UNKNOWN": 0, "FAIL": 1, "unevaluated": 1, "all": 4}
    assert (await get(client, eligibility="unevaluated"))["total"] == 1


async def test_latest_evaluation_wins(client):
    jid = await job("Re-evaluated", "FAIL", 40)
    async with AsyncSessionLocal() as s:
        later = datetime.utcnow() + timedelta(minutes=5)
        s.add(EligibilityResult(id=str(uuid.uuid4()), job_id=jid, overall_status="PASS", created_at=later))
        s.add(MatchResult(id=str(uuid.uuid4()), job_id=jid, overall_score=82, recommendation="Apply", created_at=later))
        await s.commit()
    d = await get(client)
    assert d["total"] == 1
    assert d["items"][0]["eligibility_status"] == "PASS" and d["items"][0]["match_score"] == 82


async def test_search_remote_expired_tracked(client):
    await job("Backend Intern", "PASS", 80, company="Zeta")
    await job("Frontend Intern", work_mode="Remote", location="Remote")
    await job("Old role", status="expired")
    t = await job("Tracked role", "PASS", 75, tracked_stage="submitted")
    assert [i["title"] for i in (await get(client, q="zeta"))["items"]] == ["Backend Intern"]
    assert [i["title"] for i in (await get(client, remote_only="true"))["items"]] == ["Frontend Intern"]
    assert (await get(client))["total"] == 3
    assert (await get(client, include_expired="true"))["total"] == 4
    tr = (await get(client, tracked="yes"))["items"]
    assert [i["id"] for i in tr] == [t] and tr[0]["application_stage_label"] == "Submitted"
    assert (await get(client, tracked="no"))["total"] == 2


async def test_pagination_and_sorts(client):
    ids = [await job(f"J{i}", "PASS", 50 + i, age_h=i) for i in range(25)]
    p1 = await get(client, page_size=10)
    p3 = await get(client, page_size=10, page=3)
    assert p1["total"] == 25 and p1["pages"] == 3 and len(p1["items"]) == 10 and len(p3["items"]) == 5
    assert p1["items"][0]["title"] == "J24"                       # highest score
    assert (await get(client, sort="newest"))["items"][0]["title"] == "J0"   # most recent fetch
    assert (await get(client, page=99, page_size=10))["page"] == 3            # clamped
    assert len({i["id"] for p in (1, 2, 3) for i in (await get(client, page=p, page_size=10))["items"]}) == 25


async def test_bad_params_rejected(client):
    for params in ({"eligibility": "MAYBE"}, {"sort": "random"}, {"page_size": 500}, {"tracked": "x"}):
        assert (await client.get("/api/jobs/opportunities", params=params)).status_code == 422


# --------------------------------------------------------------------------- PWA served by the backend
import json
import os

import backend.main as main_mod

DIST = main_mod.frontend_dist_dir
needs_build = pytest.mark.skipif(not os.path.exists(os.path.join(DIST, "index.html")),
                                 reason="frontend not built (cd frontend && npm run build)")


@needs_build
async def test_pwa_files_and_relative_paths(client):
    html = (await client.get("/ui/")).text
    assert 'href="manifest.json"' in html and 'href="apple-touch-icon.png"' in html
    assert "fonts.googleapis.com" not in html                 # fonts are bundled
    assert "user-scalable=no" not in html                     # zoom stays allowed
    m = (await client.get("/ui/manifest.json")).json()
    assert m["start_url"] == "./" and m["scope"] == "./"
    for icon in m["icons"]:
        r = await client.get(f"/ui/{icon['src']}")
        assert r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert {i["purpose"] for i in m["icons"]} == {"any", "maskable"}
    r = await client.get("/ui/apple-touch-icon.png")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    sw = (await client.get("/ui/sw.js")).text
    assert "network-first" in sw.lower() and "/api/" in sw
    assert (await client.get("/sw.js")).text == sw             # root copy replaces the old cache-first worker


@needs_build
async def test_root_redirects_browsers_but_not_api_clients(client):
    r = await client.get("/", headers={"accept": "text/html,application/xhtml+xml"})
    assert r.status_code == 307 and r.headers["location"] == "/ui/"
    r = await client.get("/", headers={"accept": "application/json"})
    assert r.status_code == 200 and r.json()["ui"] == "/ui"


async def test_network_info_reports_scheme(client):
    d = (await client.get("/api/network/info")).json()
    assert d["mobile_access_url"].startswith("https://" if d["https"] else "http://")
    assert d["mobile_access_url"].endswith(":5173")
    assert any("start.bat" in s for s in d["setup_instructions"])
