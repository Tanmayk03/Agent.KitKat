"""
Stage 4 tests: requirement evidence, 10-dimension eligibility, explainable matching,
profile validation and resume-to-profile import with review.
"""

import uuid

import pytest
from sqlalchemy import select

from backend.agents.requirements import extract_requirements
from backend.database.db import AsyncSessionLocal
from backend.database.models import Job, Resume, UserProfile
from backend.tools.resume_profile_extractor import extract_profile_facts

pytestmark = pytest.mark.asyncio

SAMPLE_RESUME = """TANMAY EXAMPLE
+91 98765 43210 | someone@example.com | linkedin.com/in/someone | github.com/someone
EDUCATION
SRM Institute of Science and Technology, Delhi NCR
B.Tech in Computer Science and Engineering (Data Science) | 2023 – 2027 | CGPA: 8.44/10
PROJECTS
Agent KitKat | Python, FastAPI, React
• Built a local job assistant using FastAPI and React with SQLite.
Smart Parking App
• Android app with Firebase and Java.
SKILLS
Python, Java, React, SQL, Docker
"""


# --------------------------------------------------------------------------- helpers
async def set_profile(**changes):
    async with AsyncSessionLocal() as s:
        from backend.services.profile_service import ProfileService
        p = await ProfileService.get_or_create_profile(s)
        for k, v in changes.items():
            if k.startswith("edu_"):
                p.education = {**(p.education or {}), k[4:]: v}
            else:
                setattr(p, k, v)
        await s.commit()


async def evaluate(text, title="Software Engineer Intern", **job_kw):
    from backend.services.matching_service import MatchingService
    from backend.tools.resume_parser import ResumeParser
    data = dict(id=str(uuid.uuid4()), company="Acme", title=title, url=f"https://x/{uuid.uuid4()}",
                location="Bangalore, India", work_mode="Onsite", raw_text=text, source="manual_text",
                required_skills=ResumeParser.extract_skills(text))  # as the job reader / discovery would store
    data.update(job_kw)
    async with AsyncSessionLocal() as s:
        s.add(Job(**data))
        await s.commit()
        return await MatchingService.evaluate_job(s, data["id"]), data["id"]


async def add_resume(text=SAMPLE_RESUME, active=True) -> str:
    from backend.tools.resume_parser import ResumeParser
    rid = str(uuid.uuid4())
    sections = ResumeParser.segment_sections(text)
    async with AsyncSessionLocal() as s:
        s.add(Resume(id=rid, file_name="cv.pdf", file_path="/nonexistent/cv.pdf", file_type="pdf", raw_text=text,
                     structured_data={"extracted_skills": ResumeParser.extract_skills(text), **sections}, is_active=active))
        p = (await s.execute(select(UserProfile))).scalars().first()
        if p is None:
            from backend.services.profile_service import ProfileService
            p = await ProfileService.get_or_create_profile(s)
        if active:
            p.active_resume_id = rid
        await s.commit()
    return rid


# --------------------------------------------------------------------------- requirement extraction
async def test_excluded_batches_are_not_treated_as_eligible():
    r = extract_requirements("Strictly for 2024 and 2025 graduates only. 2026/2027 students are not eligible.")
    assert r.graduation_years.value == [2024, 2025]
    assert r.graduation_years.provenance == "explicit" and "2024 and 2025" in r.graduation_years.evidence


@pytest.mark.parametrize("text,field,value", [
    ("Candidates must have no active backlogs.", "max_backlogs", 0),
    ("Maximum 1 backlog allowed at the time of joining.", "max_backlogs", 1),
    ("You must be authorized to work in the United States.", "work_authorization", "United States"),
    ("We are unable to sponsor visas for this role.", "no_sponsorship", True),
    ("Candidates must be willing to relocate to Pune.", "relocation", True),
    ("This is a 6 month internship based in Noida.", "internship_duration", "6 month"),
    ("Minimum CGPA of 7.5 required.", "min_cgpa", 7.5),
    ("Requires 3+ years of experience with Java.", "experience_years", 3),
])
async def test_requirement_patterns_with_evidence(text, field, value):
    req = getattr(extract_requirements(text), field)
    assert req.value == value and req.provenance == "explicit" and req.evidence


async def test_percentage_cutoff_needs_a_human():
    r = extract_requirements("60% or above throughout 10th, 12th and graduation.")
    assert r.min_cgpa.provenance == "explicit" and r.min_cgpa.value is None


async def test_nothing_stated_means_missing():
    r = extract_requirements("We build developer tools. Join us!")
    assert r.min_cgpa.provenance == "missing" and r.graduation_years.value is None and r.max_backlogs.value is None


# --------------------------------------------------------------------------- eligibility
async def test_ten_dimensions_with_labels():
    res, _ = await evaluate("Batch 2027 eligible. Python, React.")
    assert list(res.eligibility.checks) == ["degree", "graduation", "cgpa", "backlogs", "experience_level", "skills",
                                            "location", "work_mode", "work_authorization", "other"]
    assert all(c.label for c in res.eligibility.checks.values())
    assert res.eligibility.overall_status == "PASS"


async def test_backlog_rule_against_profile():
    text = "Batch 2027. No active backlogs."
    res, _ = await evaluate(text)
    assert res.eligibility.checks["backlogs"].status == "UNKNOWN"  # profile does not say
    await set_profile(edu_active_backlogs=0)
    assert (await evaluate(text))[0].eligibility.checks["backlogs"].status == "PASS"
    await set_profile(edu_active_backlogs=2)
    res, _ = await evaluate(text)
    assert res.eligibility.checks["backlogs"].status == "FAIL" and res.eligibility.overall_status == "FAIL"


async def test_work_authorisation_against_profile():
    text = "Batch 2027. Must be authorized to work in the United States."
    assert (await evaluate(text))[0].eligibility.checks["work_authorization"].status == "UNKNOWN"
    await set_profile(work_authorized_countries=["India"])
    res, _ = await evaluate(text)
    assert res.eligibility.checks["work_authorization"].status == "FAIL"
    assert "United States" in res.eligibility.checks["work_authorization"].evidence


async def test_relocation_makes_overall_unknown_and_skills_are_advisory():
    res, _ = await evaluate("Batch 2027. Must be willing to relocate. Kubernetes, Rust, Scala.")
    checks = res.eligibility.checks
    assert checks["other"].status == "UNKNOWN" and res.eligibility.overall_status == "UNKNOWN"
    assert checks["skills"].status == "FAIL" and checks["skills"].hard is False


async def test_skills_alone_never_fail_eligibility():
    res, _ = await evaluate("Batch 2027 eligible. Kubernetes, Rust.")
    assert res.eligibility.checks["skills"].status == "FAIL"
    assert res.eligibility.overall_status == "PASS"


async def test_evaluation_roundtrip_keeps_checks_and_explanations(client):
    _, job_id = await evaluate("Batch 2027. Minimum CGPA of 9.0. Python.")
    data = (await client.get(f"/api/matching/evaluation/{job_id}")).json()
    cg = data["eligibility"]["checks"]["cgpa"]
    assert cg["status"] == "FAIL" and "9.0" in cg["evidence"] and cg["candidate_value"] == "8.44"
    assert data["next_action"].startswith("Skip")
    assert data["recommendation"] == "INELIGIBLE"
    assert set(data["factor_explanations"]) == {"technical_skills", "education_and_graduation",
                                                "projects_and_experience", "role_relevance", "location"}


# --------------------------------------------------------------------------- matching
async def test_project_relevance_comes_from_real_overlap():
    await set_profile(verified_skills=["Python", "React"])
    res, _ = await evaluate("Batch 2027. Python, React, Docker.")
    assert res.category_scores.projects_and_experience == 0.0
    assert "no projects" in res.factor_explanations["projects_and_experience"]

    await set_profile(projects=[{"name": "Agent KitKat", "description": "FastAPI + React app", "tech_stack": ["Python", "React"]}])
    res, _ = await evaluate("Batch 2027. Python, React, Docker.")
    assert res.category_scores.projects_and_experience == pytest.approx(13.33, abs=0.01)  # 2 of 3 job skills
    assert res.relevant_projects == ["Project: Agent KitKat"]


async def test_no_listed_skills_marks_factors_na_and_rescales():
    res, _ = await evaluate("Batch 2027 eligible. Great team.")
    assert set(res.na_factors) == {"technical_skills", "projects_and_experience"}
    cs = res.category_scores
    expected = round((cs.education_and_graduation + cs.role_relevance + cs.location) / 45 * 100, 1)
    assert res.overall_score == expected


async def test_next_action_for_unknown_and_pass():
    res, _ = await evaluate("Python, React.")  # batch not stated
    assert res.next_action.startswith("Verify first")
    await set_profile(verified_skills=["Python", "React"],
                      projects=[{"name": "P", "description": "", "tech_stack": ["Python", "React"]}])
    res, _ = await evaluate("Batch 2027. Python, React.")
    assert res.eligibility.overall_status == "PASS" and res.next_action.startswith("Prepare")


# --------------------------------------------------------------------------- profile validation / import
async def test_extractor_reads_resume_with_evidence():
    facts = {f["field"]: f for f in extract_profile_facts(SAMPLE_RESUME)}
    assert facts["education.cgpa"]["suggested"] == 8.44 and "CGPA: 8.44" in facts["education.cgpa"]["evidence"]
    assert facts["education.graduation_year"]["suggested"] == 2027
    assert facts["education.degree"]["suggested"] == "B.Tech"
    assert facts["phone"]["suggested"] == "+919876543210"
    assert facts["linkedin_url"]["suggested"] == "https://linkedin.com/in/someone"
    assert [p["name"] for p in facts["projects"]["suggested"]] == ["Agent KitKat", "Smart Parking App"]
    assert "Java" in facts["projects"]["suggested"][1]["tech_stack"]


async def test_completeness_flags_cgpa_that_differs_from_resume(client):
    await client.get("/api/profile")
    await set_profile(edu_cgpa=8.53)
    await add_resume()
    data = (await client.get("/api/profile/completeness")).json()
    msgs = [w["message"] for w in data["warnings"] if w["field"] == "education.cgpa"]
    assert any("8.53" in m and "8.44" in m for m in msgs)
    assert data["complete"] is False


async def test_completeness_without_resume(client):
    data = (await client.get("/api/profile/completeness")).json()
    fields = {w["field"] for w in data["warnings"]}
    assert {"active_resume_id", "education.active_backlogs", "work_authorized_countries", "projects"} <= fields


async def test_resume_import_applies_only_selected_fields(client):
    await client.get("/api/profile")
    await set_profile(edu_cgpa=8.53, phone="+91-0000000000")
    rid = await add_resume()
    sugg = {s["field"]: s for s in (await client.get(f"/api/profile/resume-suggestions/{rid}")).json()}
    assert sugg["education.cgpa"]["current"] == 8.53 and sugg["education.cgpa"]["differs"] is True

    r = await client.post("/api/profile/apply-resume-suggestions",
                          json={"resume_id": rid, "fields": ["education.cgpa", "verified_skills", "projects"]})
    assert r.status_code == 200
    p = r.json()
    assert p["education"]["cgpa"] == 8.44
    assert p["phone"] == "+91-0000000000"  # not selected -> untouched
    assert {"Python", "React", "Java"} <= set(p["verified_skills"])
    assert "Python" not in p["unverified_skills"]
    assert len(p["projects"]) == 2
    assert (await client.get("/api/profile/resume-suggestions/nope")).status_code == 404


async def test_title_and_company_found_without_the_language_model(client):
    r = await client.post("/api/jobs/analyze-text", json={
        "text": "Software Engineer Intern - Acme Labs\nLocation: Bengaluru, India\nBatch 2027. Skills: Python, React"})
    ex = r.json()["extracted"]
    assert ex["job_title"] == "Software Engineer Intern" and ex["company_name"] == "Acme Labs"
    assert ex["work_location"] == "Bengaluru, India"
