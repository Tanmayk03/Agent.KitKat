"""
Opportunities list: every stored job joined with its latest eligibility and match result
and (if tracked) its application. Filtering, sorting and pagination happen in SQL so the
page stays fast with thousands of jobs.
"""

from typing import Any, Dict, Optional

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Application, EligibilityResult, Job, MatchResult
from backend.services.lifecycle import stage_label
from backend.services.profile_service import ProfileService

ELIGIBILITY_FILTERS = ("all", "PASS", "UNKNOWN", "FAIL", "unevaluated")
SORTS = ("best", "score", "newest", "posted")


def _latest(model):
    """Subquery: newest row of `model` per job_id."""
    ranked = select(
        model,
        func.row_number().over(partition_by=model.job_id, order_by=model.created_at.desc()).label("rn"),
    ).subquery()
    return ranked


async def list_opportunities(
    session: AsyncSession,
    q: str = "",
    eligibility: str = "all",
    remote_only: bool = False,
    include_expired: bool = False,
    tracked: str = "all",          # all | yes | no
    sort: str = "best",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    el_sq = _latest(EligibilityResult)
    mr_sq = _latest(MatchResult)
    el = el_sq.c
    mr = mr_sq.c

    base = (
        select(
            Job,
            el.overall_status, el.rejection_reasons, el.unverified_requirements,
            mr.overall_score, mr.recommendation, mr.matching_skills, mr.missing_skills, mr.details_json,
            Application.id, Application.stage,
        )
        .outerjoin(el_sq, and_(el.job_id == Job.id, el.rn == 1))
        .outerjoin(mr_sq, and_(mr.job_id == Job.id, mr.rn == 1))
        .outerjoin(Application, Application.job_id == Job.id)
    )

    conds = []
    if q.strip():
        like = f"%{q.strip().lower()}%"
        conds.append(or_(func.lower(Job.title).like(like), func.lower(Job.company).like(like),
                         func.lower(Job.location).like(like)))
    if remote_only:
        conds.append(or_(func.lower(Job.work_mode) == "remote", func.lower(Job.location).like("%remote%")))
    if not include_expired:
        conds.append(or_(Job.status.is_(None), Job.status != "expired"))
    if tracked == "yes":
        conds.append(Application.id.is_not(None))
    elif tracked == "no":
        conds.append(Application.id.is_(None))

    # Facet counts use every filter except eligibility, so the chips show what each choice would give.
    facet_q = base.where(*conds).subquery()
    key = func.coalesce(facet_q.c.overall_status, "unevaluated").label("k")
    facet_rows = (await session.execute(select(key, func.count()).group_by(key))).all()
    facets = {k: 0 for k in ("PASS", "UNKNOWN", "FAIL", "unevaluated")}
    for k, n in facet_rows:
        facets[k] = n
    facets["all"] = sum(facets.values())

    if eligibility in ("PASS", "UNKNOWN", "FAIL"):
        conds.append(el.overall_status == eligibility)
    elif eligibility == "unevaluated":
        conds.append(el.overall_status.is_(None))

    tier = case((el.overall_status == "PASS", 0), (el.overall_status == "UNKNOWN", 1),
                (el.overall_status == "FAIL", 3), else_=2)
    newest = func.coalesce(Job.fetched_at, Job.created_at)
    order = {
        "best": [tier, mr.overall_score.is_(None), mr.overall_score.desc(), newest.desc()],
        "score": [mr.overall_score.is_(None), mr.overall_score.desc(), newest.desc()],
        "newest": [newest.desc()],
        "posted": [Job.posted_at.is_(None), Job.posted_at.desc(), newest.desc()],
    }[sort if sort in SORTS else "best"]

    total = (await session.execute(select(func.count()).select_from(base.where(*conds).subquery()))).scalar_one()
    page_size = max(1, min(page_size, 100))
    pages = max(1, -(-total // page_size))
    page = max(1, min(page, pages))
    rows = (await session.execute(
        base.where(*conds).order_by(*order).offset((page - 1) * page_size).limit(page_size)
    )).all()

    profile = await ProfileService.get_or_create_profile(session)
    min_score = float((profile.application_preferences or {}).get("min_match_score", 75))

    items = []
    for (job, el_status, rejections, unverified, score, rec, matching, missing, details,
         app_id, app_stage) in rows:
        reasons = []
        if el_status == "FAIL":
            reasons = list(rejections or [])[:3]
        elif el_status == "UNKNOWN":
            reasons = list(unverified or [])[:3]
        items.append({
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location or "Not stated",
            "work_mode": job.work_mode or "Unknown",
            "url": job.url,
            "source": job.source,
            "status": job.status,
            "salary_stipend": job.salary_stipend,
            "employment_type": job.employment_type,
            "posted_at": job.posted_at,
            "fetched_at": job.fetched_at or job.created_at,
            "description": (job.description or "")[:400],
            "eligibility_status": el_status,
            "eligibility_reasons": reasons,
            "match_score": round(score, 1) if score is not None else None,
            "above_threshold": score is not None and el_status == "PASS" and score >= min_score,
            "recommendation": rec,
            "matching_skills": list(matching or [])[:6],
            "missing_skills": list(missing or [])[:6],
            "next_action": (details or {}).get("next_action"),
            "application_id": app_id,
            "application_stage": app_stage,
            "application_stage_label": stage_label(app_stage) if app_stage else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages,
            "facets": facets, "min_match_score": min_score}
