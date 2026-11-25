"""
Agent KitKat - Resume Matching Agent

Deterministic, explainable 5-factor score:
  Skills 35 · Education & graduation 20 · Projects & experience 20 · Role relevance 15 · Location 10

- Every factor comes with a sentence explaining its points.
- A factor that cannot be assessed (e.g. the posting lists no recognisable skills) is marked N/A and
  the remaining weights are rescaled to 100, instead of awarding invented baseline points.
- Projects score from real overlap between the job's skills and each project's tech stack /
  description (profile projects + resume project lines). No credit just for "having projects".
- A hard eligibility failure always gives recommendation INELIGIBLE, whatever the score.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.database.models import Job, UserProfile, Resume
from backend.schemas.matching import EligibilityResponse, MatchCategoryScores, MatchResponse
from backend.tools.job_discovery_sources import classify_location
from backend.tools.resume_parser import ResumeParser
from backend.agents.eligibility_agent import (
    EligibilityAgent,
    SENIOR_ROLE_KEYWORDS,
    INTERN_FRESHER_KEYWORDS,
)

logger = logging.getLogger("agent_kitkat.matching_agent")

WEIGHTS = {"technical_skills": 35.0, "education_and_graduation": 20.0, "projects_and_experience": 20.0,
           "role_relevance": 15.0, "location": 10.0}
TECH_TITLE_WORDS = ["software", "developer", "engineer", "frontend", "backend", "full stack", "ai", "ml", "data", "sde", "python", "java", "react"]


def candidate_skill_set(profile: UserProfile, resume: Optional[Resume]) -> List[str]:
    """Skills that count for matching: verified profile skills + skills found in the selected resume."""
    skills = {s for s in (profile.verified_skills or [])}
    if resume and resume.structured_data:
        skills.update(resume.structured_data.get("extracted_skills", []) or [])
    return sorted(skills)


def _evidence_items(profile: UserProfile, resume: Optional[Resume]) -> List[Tuple[str, set]]:
    """(name, skills) for each project / experience entry we can see."""
    items: List[Tuple[str, set]] = []
    for p in (profile.projects or []):
        if isinstance(p, dict):
            name = (p.get("name") or p.get("title") or "").strip()
            blob = " ".join([name, p.get("description") or "", " ".join(p.get("tech_stack") or [])])
        else:
            name, blob = str(p).strip()[:80], str(p)
        if name:
            items.append((f"Project: {name}", set(ResumeParser.extract_skills(blob))))
    for w in (profile.work_experience or []):
        if isinstance(w, dict):
            name = " - ".join(x for x in (w.get("role"), w.get("company")) if x)
            blob = " ".join([name, w.get("description") or ""])
            if name:
                items.append((f"Experience: {name}", set(ResumeParser.extract_skills(blob))))
    if resume and resume.structured_data:
        for section, label in (("projects", "Resume project"), ("experience", "Resume experience")):
            for line in resume.structured_data.get(section, []) or []:
                if isinstance(line, str) and len(line) > 5:
                    clean = re.sub(r"^[\s•\-*–▪●◦]+", "", line).strip()
                    found = set(ResumeParser.extract_skills(clean))
                    if found:
                        items.append((f"{label}: {clean[:80]}", found))
    return items


class MatchingAgent:
    """Calculates weighted, explainable match scores between your profile/resume and a job."""

    @classmethod
    def evaluate_job(cls, job: Job, profile: UserProfile, resume: Optional[Resume] = None,
                     min_score: float = 75.0) -> MatchResponse:
        cand_skills = candidate_skill_set(profile, resume)
        eligibility: EligibilityResponse = EligibilityAgent.verify_eligibility(job, profile, cand_skills)
        have = {s.lower() for s in cand_skills}
        explain: Dict[str, str] = {}
        na: List[str] = []

        # 1. Skills (35) -------------------------------------------------------------------
        job_skills = job.required_skills or []
        matching_skills = [s for s in job_skills if s.lower() in have]
        missing_skills = [s for s in job_skills if s.lower() not in have]
        if job_skills:
            tech = round(len(matching_skills) / len(job_skills) * 35.0, 2)
            explain["technical_skills"] = (f"{len(matching_skills)} of {len(job_skills)} listed skills are verified for you "
                                           f"({len(matching_skills)}/{len(job_skills)} × 35).")
        else:
            tech = 0.0
            na.append("technical_skills")
            explain["technical_skills"] = "N/A: no recognisable skills in the posting text. Analyse the full job page for a better estimate."

        # 2. Education & graduation (20): degree, graduation, CGPA checks ----------------------
        edu_checks = [eligibility.degree, eligibility.graduation, eligibility.cgpa]
        if any(c.status == "FAIL" for c in edu_checks):
            edu = 0.0
            explain["education_and_graduation"] = "0: an education requirement is not met (" + "; ".join(
                c.details for c in edu_checks if c.status == "FAIL") + ")."
        else:
            passed = sum(1 for c in edu_checks if c.status == "PASS")
            edu = round(20.0 * passed / 3, 2)
            unknown = [c.label or "" for c in edu_checks if c.status == "UNKNOWN"]
            explain["education_and_graduation"] = (f"{passed} of 3 education checks passed ({passed}/3 × 20)"
                                                   + (f"; unverified: {', '.join(unknown)}." if unknown else "."))

        # 3. Projects & experience (20): real overlap with the job's skills ---------------------
        items = _evidence_items(profile, resume)
        relevant_projects: List[str] = []
        if not job_skills:
            proj = 0.0
            na.append("projects_and_experience")
            explain["projects_and_experience"] = "N/A: the posting lists no skills to compare your projects against."
        elif not items:
            proj = 0.0
            explain["projects_and_experience"] = "0: no projects or experience in your profile/resume to compare. Add your projects on the Profile page."
        else:
            job_set = {s.lower() for s in job_skills}
            scored = sorted(((len({s.lower() for s in sk} & job_set), name, sk) for name, sk in items), reverse=True)
            best = scored[0][0]
            target = min(3, len(job_set))
            proj = round(20.0 * min(1.0, best / target), 2) if target else 0.0
            relevant_projects = list(dict.fromkeys(name for n, name, _ in scored if n > 0))[:5]
            explain["projects_and_experience"] = (
                f"Best match uses {best} of the job's skills (target {target}): {scored[0][1]} ({min(best, target)}/{target} × 20)."
                if best else "0: none of your projects/experience use the job's listed skills.")

        # 4. Role relevance (15) --------------------------------------------------------------------
        title = (job.title or "").lower()
        preferred = [r.lower() for r in (profile.preferred_roles or [])]
        is_senior = any(re.search(p, title) for p in SENIOR_ROLE_KEYWORDS)
        is_early = any(re.search(p, title) for p in INTERN_FRESHER_KEYWORDS)
        is_tech = any(k in title for k in TECH_TITLE_WORDS)
        if is_senior:
            role, why = 0.0, "senior-level title"
        elif any(p and p in title for p in preferred):
            role, why = 15.0, "title matches one of your preferred roles"
        elif is_early and is_tech:
            role, why = 15.0, "early-career technical role"
        elif is_early:
            role, why = 10.0, "early-career, but not clearly a technical role"
        elif is_tech:
            role, why = 5.0, "technical role, but not marked intern/fresher/entry-level"
        else:
            role, why = 0.0, "not a technical role you target"
        explain["role_relevance"] = f"{role:g}/15: {why} ('{job.title}')."

        # 5. Location (10) ---------------------------------------------------------------------------
        loc_status = eligibility.location.status
        category, _ = classify_location(job.location or "", job.work_mode or "")
        if loc_status != "PASS":
            loc = 0.0
        else:
            loc = 10.0 if category == "india" else 9.0
        explain["location"] = f"{loc:g}/10: {eligibility.location.details}"

        # Overall with N/A rescaling -------------------------------------------------------------------
        scores = {"technical_skills": tech, "education_and_graduation": edu, "projects_and_experience": proj,
                  "role_relevance": role, "location": loc}
        available = sum(w for k, w in WEIGHTS.items() if k not in na)
        overall = round(sum(v for k, v in scores.items() if k not in na) / available * 100.0, 1) if available else 0.0
        overall = max(0.0, min(100.0, overall))

        # Recommendation + next action ------------------------------------------------------------
        status = eligibility.overall_status
        if status == "FAIL" or is_senior:
            recommendation = "INELIGIBLE"
            next_action = f"Skip: {eligibility.rejection_reasons[0] if eligibility.rejection_reasons else 'senior-level role'}"
        elif status == "UNKNOWN":
            recommendation = "CONSIDER_WITH_VERIFICATION" if overall >= 70.0 and is_early else "NEEDS_VERIFICATION"
            next_action = f"Verify first: {eligibility.unverified_requirements[0]}" if eligibility.unverified_requirements else "Verify the posting details."
        else:
            if overall >= max(min_score, 75.0) and is_early:
                recommendation = "STRONGLY_RECOMMENDED"
            elif overall >= 65.0 and is_early:
                recommendation = "RECOMMENDED"
            elif overall >= 50.0:
                recommendation = "CONSIDER"
            else:
                recommendation = "NOT_RECOMMENDED"
            if overall >= min_score:
                next_action = "Prepare an application draft and review it."
            elif missing_skills:
                next_action = f"Below your {min_score:g}% threshold. Main gaps: {', '.join(missing_skills[:3])}. Apply only if you can show these."
            else:
                next_action = f"Below your {min_score:g}% threshold. Apply only if the role really interests you."

        lines = [f"Overall Match Score: {overall}% | Eligibility: {status} | Recommendation: {recommendation}"]
        labels = {"technical_skills": "Technical Skills", "education_and_graduation": "Education & Graduation",
                  "projects_and_experience": "Projects & Experience", "role_relevance": "Role Relevance", "location": "Location"}
        for k, label in labels.items():
            pts = "N/A" if k in na else f"{scores[k]:g}/{WEIGHTS[k]:g}"
            lines.append(f"- {label} ({pts}): {explain[k]}")
        if na:
            lines.append(f"Rescaled to 100 over the {len(WEIGHTS) - len(na)} assessable factors.")
        if eligibility.rejection_reasons:
            lines.append("Hard Rejection Reasons: " + " | ".join(eligibility.rejection_reasons))
        if eligibility.unverified_requirements:
            lines.append("Pending Verification: " + " | ".join(eligibility.unverified_requirements))
        lines.append(f"Next action: {next_action}")

        return MatchResponse(
            job_id=job.id,
            resume_id=resume.id if resume else None,
            overall_score=overall,
            category_scores=MatchCategoryScores(**scores),
            matching_skills=matching_skills,
            missing_skills=missing_skills,
            relevant_projects=relevant_projects,
            recommendation=recommendation,
            explanation="\n".join(lines),
            factor_explanations=explain,
            na_factors=na,
            next_action=next_action,
            eligibility=eligibility,
        )
