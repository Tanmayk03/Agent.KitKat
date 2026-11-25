"""
Stage 5 tests: grounding checker, draft versions, approval gate, application lifecycle,
tracker search, duplicate protection.
"""

import uuid

import pytest
from sqlalchemy import select

from backend.agents.grounding import check_text
from backend.database.db import AsyncSessionLocal
from backend.database.models import Application, Job

pytestmark = pytest.mark.asyncio

FILLED = {"why_join": "I like the product.", "relevant_project": "A course project for my college.",
          "availability": "From June 2026", "salary_expectation": "As per company norms"}


async def make_job(**kw) -> str:
    data = dict(id=str(uuid.uuid4()), company="Acme", title="Software Engineer Intern", url=f"https://x/{uuid.uuid4()}",
                location="Bangalore, India", work_mode="Onsite", raw_text="Batch 2027. Python, React.",
                required_skills=["Python", "React"], source="manual_text", graduation_eligibility=[2027])
    data.update(kw)
    async with AsyncSessionLocal() as s:
        s.add(Job(**data))
        await s.commit()
    return data["id"]


async def prepared(client, **job_kw):
    job_id = await make_job(**job_kw)
    d = (await client.post(f"/api/applications/prepare/{job_id}", json={})).json()
    approvals = (await client.get("/api/applications/approvals")).json()
    appr = next(a for a in approvals if a["draft_id"] == d["id"])
    return job_id, d, appr["id"]


async def app_for(client, job_id):
    items = (await client.get("/api/applications", params={"page_size": 100})).json()["items"]
    return next(i for i in items if i["job_id"] == job_id)


# --------------------------------------------------------------------------- grounding
def _check(text, **kw):
    args = dict(candidate_skills=["Python", "React"], corpus="Python React FastAPI 2027 8.44 hackathon winner 3 hackathons",
                profile_cgpa=8.44, has_certifications=False, company="Acme")
    args.update(kw)
    return {i["kind"] for i in check_text(text, "cover_letter", **args)}


async def test_grounding_flags_unsupported_claims():
    assert "skill" in _check("I have built Kubernetes clusters.")
    assert "number" in _check("I improved latency by 40%.")
    assert "number" not in _check("I won 3 hackathons.")             # in the corpus
    assert "employer" in _check("I interned at Google last summer.")
    assert "employer" not in _check("I would love to work at Acme.")  # the company being applied to
    assert "cgpa" in _check("My CGPA is 9.1.")
    assert "cgpa" not in _check("My CGPA is 8.44.")
    assert "certification" in _check("I am AWS certified.")
    assert "placeholder" in _check("[Add a reason here]")
    assert _check("I enjoy building with Python and React.") == set()


# --------------------------------------------------------------------------- versions
async def test_versions_are_kept_and_restorable(client):
    _, d, _ = await prepared(client)
    assert d["current_version"] == 1 and any(i["kind"] == "placeholder" for i in d["grounding_report"])
    e = (await client.put(f"/api/applications/drafts/{d['id']}", json={"custom_answers": FILLED})).json()
    assert e["current_version"] == 2 and e["grounding_report"] == []
    # no-op edit does not create a version
    assert (await client.put(f"/api/applications/drafts/{d['id']}", json={"custom_answers": FILLED})).json()["current_version"] == 2
    r = (await client.post(f"/api/applications/drafts/{d['id']}/versions/1/restore")).json()
    assert r["current_version"] == 3 and r["custom_answers"]["availability"] == "NEEDS_YOUR_INPUT"
    versions = (await client.get(f"/api/applications/drafts/{d['id']}/versions")).json()
    assert [(v["version"], v["source"]) for v in versions] == [(3, "restored"), (2, "edited"), (1, "generated")]


# --------------------------------------------------------------------------- approval gate
async def test_approval_blocked_by_flagged_claims_unless_acknowledged(client):
    job_id, d, appr_id = await prepared(client)
    r = await client.post(f"/api/applications/approvals/{appr_id}/decide", json={"action": "approve"})
    assert r.status_code == 409 and "could not be traced" in r.json()["detail"]
    r = await client.post(f"/api/applications/approvals/{appr_id}/decide",
                          json={"action": "approve", "acknowledge_unverified_claims": True})
    assert r.status_code == 200
    app = await app_for(client, job_id)
    events = (await client.get(f"/api/applications/{app['id']}/events")).json()
    assert "acknowledged" in events[-1]["note"]


async def test_editing_an_approved_draft_requires_reapproval(client):
    job_id, d, appr_id = await prepared(client)
    await client.put(f"/api/applications/drafts/{d['id']}", json={"custom_answers": FILLED})
    assert (await client.post(f"/api/applications/approvals/{appr_id}/decide", json={"action": "approve"})).status_code == 200
    assert (await app_for(client, job_id))["stage"] == "draft_ready"
    await client.put(f"/api/applications/drafts/{d['id']}", json={"cover_letter": "A new letter."})
    app = await app_for(client, job_id)
    assert app["stage"] == "awaiting_approval" and app["approval_status"] == "pending"


# --------------------------------------------------------------------------- lifecycle
async def test_full_lifecycle_with_history(client):
    job_id, d, appr_id = await prepared(client)
    await client.put(f"/api/applications/drafts/{d['id']}", json={"custom_answers": FILLED})
    await client.post(f"/api/applications/approvals/{appr_id}/decide", json={"action": "approve"})
    app = await app_for(client, job_id)
    assert app["stage"] == "draft_ready" and app["applied_at"] is None

    r = await client.patch(f"/api/applications/{app['id']}", json={"stage": "submitted", "note": "Applied manually on the careers site"})
    assert r.status_code == 200 and r.json()["applied_at"] is not None
    r = await client.patch(f"/api/applications/{app['id']}", json={"stage": "application_confirmed", "confirmation_id": "ACME-123",
                                                                   "follow_up_date": "2026-12-10", "notes": "Recruiter: Priya"})
    body = r.json()
    assert body["stage_label"] == "Application Confirmed" and body["confirmation_id"] == "ACME-123"
    assert body["follow_up_date"] == "2026-12-10" and "interview" in body["allowed_next_stages"]

    for stage in ("interview", "rejected"):
        assert (await client.patch(f"/api/applications/{app['id']}", json={"stage": stage})).status_code == 200
    r = await client.patch(f"/api/applications/{app['id']}", json={"stage": "interview"})
    assert r.status_code == 422 and "Cannot move" in r.json()["detail"]  # rejected is final

    stages = [(e["from_stage"], e["to_stage"]) for e in (await client.get(f"/api/applications/{app['id']}/events")).json()]
    assert stages[-4:] == [("draft_ready", "submitted"), ("submitted", "application_confirmed"),
                           ("application_confirmed", "interview"), ("interview", "rejected")]
    assert (await client.patch(f"/api/applications/{app['id']}", json={"follow_up_date": "10-12-2026"})).status_code == 422


async def test_sent_applications_are_frozen(client):
    job_id, d, appr_id = await prepared(client)
    app = await app_for(client, job_id)
    await client.patch(f"/api/applications/{app['id']}", json={"stage": "submitted"})
    assert (await client.post(f"/api/applications/prepare/{job_id}", json={})).status_code == 409
    assert (await client.put(f"/api/applications/drafts/{d['id']}", json={"cover_letter": "x"})).status_code == 409
    assert (await client.post(f"/api/applications/drafts/{d['id']}/versions/1/restore")).status_code == 409
    assert (await client.post(f"/api/browser/run/{d['id']}", json={"auto_submit": False})).status_code == 409


async def test_shortlist_one_application_per_job(client):
    job_id = await make_job()
    await client.post(f"/api/matching/evaluate/{job_id}")
    r = await client.post(f"/api/applications/shortlist/{job_id}")
    assert r.status_code == 200 and r.json()["stage"] == "eligible"
    assert (await client.post(f"/api/applications/shortlist/{job_id}")).status_code == 409
    await client.post(f"/api/applications/prepare/{job_id}", json={})
    items = [i for i in (await client.get("/api/applications")).json()["items"] if i["job_id"] == job_id]
    assert len(items) == 1 and items[0]["stage"] == "awaiting_approval"

    bad = await make_job(graduation_eligibility=[2024], raw_text="Only 2024 batch graduates. Python.")
    await client.post(f"/api/matching/evaluate/{bad}")
    assert (await client.post(f"/api/applications/shortlist/{bad}")).json()["stage"] == "not_eligible"


async def test_tracker_search_filter_sort_paginate(client):
    for name in ("Zeta", "Alpha", "Mid"):
        await client.post(f"/api/applications/shortlist/{await make_job(company=name)}")
    data = (await client.get("/api/applications", params={"sort": "company", "page_size": 2})).json()
    assert data["total"] == 3 and [i["company"] for i in data["items"]] == ["Alpha", "Mid"]
    assert (await client.get("/api/applications", params={"sort": "company", "page_size": 2, "page": 2})).json()["items"][0]["company"] == "Zeta"
    assert (await client.get("/api/applications", params={"q": "alp"})).json()["total"] == 1
    data = (await client.get("/api/applications", params={"stage": "withdrawn"})).json()
    assert data["total"] == 0 and sum(data["stage_counts"].values()) == 3


async def test_legacy_statuses_get_a_stage():
    from backend.database.db import _backfill_application_stages
    job_id = await make_job()
    async with AsyncSessionLocal() as s:
        app_id = str(uuid.uuid4())
        s.add(Application(id=app_id, job_id=job_id, status="submitted"))
        await s.commit()
        from sqlalchemy import text
        await s.execute(text("UPDATE applications SET stage = NULL WHERE id = :i"), {"i": app_id})
        await s.commit()
    await _backfill_application_stages()
    async with AsyncSessionLocal() as s:
        app = (await s.execute(select(Application).where(Application.job_id == job_id))).scalars().first()
    assert app.stage == "submitted"


async def test_naming_the_role_is_not_a_skill_claim():
    assert _check("I am applying for the AI/ML Intern role at Acme.", job_title="AI/ML Intern") == set()
    assert _check("Great AI team.") == set()                      # not a first-person claim
    assert "skill" in _check("I have deep Machine Learning experience.", job_title="AI/ML Intern")
