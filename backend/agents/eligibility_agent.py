"""
Agent KitKat - Eligibility Verification Agent

Compares a posting's requirements (with evidence, see agents/requirements.py) against your
stored profile, across 10 dimensions:

  1 degree   2 graduation year   3 CGPA   4 active backlogs   5 experience level
  6 skills (advisory)   7 location   8 work mode   9 work authorisation   10 other hard requirements

Rules:
- Statuses are PASS, FAIL or UNKNOWN. Unknown is never turned into PASS.
- Missing facts in YOUR profile give UNKNOWN (never a hardcoded default).
- A missing graduation batch in the posting gives UNKNOWN (internships often restrict batches silently).
- A requirement the posting does not state at all (CGPA, degree, backlogs) passes with provenance
  "missing" and a clear "not stated" note, so you can see it was not checked against anything.
- Only hard checks decide the overall result; FAIL overrides everything, then UNKNOWN.
- Every check carries the posting evidence it was based on.
"""

import re
import logging
from typing import Dict, List, Optional

from backend.database.models import Job, UserProfile
from backend.schemas.matching import RequirementCheck, EligibilityResponse
from backend.agents.requirements import extract_requirements, Requirement
from backend.tools.job_discovery_sources import classify_location

logger = logging.getLogger("agent_kitkat.eligibility_agent")

SENIOR_ROLE_KEYWORDS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\bstaff\b", r"\blead\b", r"\bprincipal\b",
    r"\barchitect\b", r"\bdirector\b", r"\bhead\b", r"\bvp\b", r"\bvice president\b",
    r"\bmanager\b", r"\bchief\b", r"\bexecutive\b", r"\btier\s*(?:ii|iii|iv|2|3|4)\b"
]

INTERN_FRESHER_KEYWORDS = [
    r"\bintern\b", r"\binternship\b", r"\bfresher\b", r"\bjunior\b", r"\bjr\.?\b",
    r"\bentry\s*-?level\b", r"\bgraduate\b", r"\bco-?op\b", r"\btrainee\b",
    r"\bapprentice\b", r"\bworking\s*student\b", r"\bwerkstudent\b", r"\bstudent\b"
]

INDIA_LOCATION_PATTERNS = [
    r"\bindia\b", r"\bbangalore\b", r"\bbengaluru\b", r"\bdelhi\b",
    r"\bnoida\b", r"\bgurgaon\b", r"\bgurugram\b", r"\bhyderabad\b",
    r"\bpune\b", r"\bmumbai\b", r"\bchennai\b", r"\bkolkata\b", r"\bjaipur\b",
    r"\bahmedabad\b", r"\bkarnataka\b", r"\bmaharashtra\b", r"\bharyana\b"
]

REMOTE_LOCATION_PATTERNS = [
    r"\bremote\b", r"\bworldwide\b", r"\banywhere\b", r"\bwork from home\b", r"\bwfh\b"
]

CHECK_LABELS = {
    "degree": "Degree",
    "graduation": "Graduation year",
    "cgpa": "CGPA",
    "backlogs": "Active backlogs",
    "experience_level": "Experience level",
    "skills": "Skills",
    "location": "Location",
    "work_mode": "Work mode",
    "work_authorization": "Work authorisation",
    "other": "Other requirements",
}


def _check(status: str, details: str, req: Optional[Requirement] = None, requirement: Optional[str] = None,
           candidate: Optional[str] = None, hard: bool = True) -> RequirementCheck:
    if requirement is None and req is not None and req.value is not None:
        requirement = str(req.value)
    return RequirementCheck(
        status=status, details=details, requirement=requirement, candidate_value=candidate,
        evidence=req.evidence if req else None,
        provenance=req.provenance if req else None,
        hard=hard,
    )


class EligibilityAgent:
    """Deterministic eligibility verification engine."""

    @staticmethod
    def verify_eligibility(job: Job, profile: UserProfile, candidate_skills: Optional[List[str]] = None) -> EligibilityResponse:
        education = profile.education or {}
        cand_degree = (education.get("degree") or "").strip() or None
        cand_spec = (education.get("specialization") or "").strip() or None

        def num(key, cast):
            try:
                v = education.get(key)
                return cast(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        cand_cgpa = num("cgpa", float)
        cand_year = num("graduation_year", int)
        cand_backlogs = num("active_backlogs", int)
        cand_countries = [c.strip().lower() for c in (getattr(profile, "work_authorized_countries", None) or []) if c]
        preferred_work_mode = (profile.work_mode or "Any").lower()

        text = "\n".join(t for t in (job.title or "", job.raw_text or job.description or "") if t)
        req = extract_requirements(text, title=job.title or "", job_fields={
            "graduation_eligibility": job.graduation_eligibility,
            "minimum_cgpa": job.minimum_cgpa,
            "required_degree": job.required_degree,
        })
        checks: Dict[str, RequirementCheck] = {}

        # 1. Degree ---------------------------------------------------------------
        d = req.degree
        if d.value is None:
            checks["degree"] = _check("PASS", "No degree requirement stated in the posting.", d, candidate=cand_degree)
        elif not cand_degree:
            checks["degree"] = _check("UNKNOWN", f"Posting asks for '{d.value}', but your degree is missing from your profile.", d)
        else:
            low = str(d.value).lower()
            if re.search(r"\bmbbs\b|\bllb\b|\blaw\b|\bca\b|\bchartered\b|ph\.?\s?d", low):
                checks["degree"] = _check("FAIL", f"Posting requires '{d.value}'; you have {cand_degree}.", d, candidate=cand_degree)
            elif re.search(r"master|m\.\s?tech|mtech|\bmca\b", low) and not re.search(r"bachelor|b\.\s?tech|btech|b\.\s?e\.", low):
                checks["degree"] = _check("UNKNOWN", f"Posting mentions '{d.value}'. Check whether a Bachelor's degree is accepted.", d,
                                          candidate=cand_degree)
            else:
                spec = f" in {cand_spec}" if cand_spec else ""
                checks["degree"] = _check("PASS", f"Your {cand_degree}{spec} meets '{d.value}'.", d, candidate=cand_degree)

        # 2. Graduation year --------------------------------------------------------
        g = req.graduation_years
        if g.value is None:
            checks["graduation"] = _check("UNKNOWN", "Eligible graduation batch is not stated in the posting. Verify before applying.",
                                          g, candidate=str(cand_year) if cand_year else None)
        elif cand_year is None:
            checks["graduation"] = _check("UNKNOWN", f"Posting requires batches {g.value}, but your graduation year is missing from your profile.", g)
        elif cand_year in g.value:
            checks["graduation"] = _check("PASS", f"Your graduation year {cand_year} is in the eligible batches {g.value}.", g, candidate=str(cand_year))
        else:
            checks["graduation"] = _check("FAIL", f"Your graduation year {cand_year} is not in the eligible batches {g.value}.", g, candidate=str(cand_year))

        # 3. CGPA ---------------------------------------------------------------------
        c = req.min_cgpa
        cgpa_str = None if cand_cgpa is None else str(cand_cgpa)
        if c.provenance == "missing":
            checks["cgpa"] = _check("PASS", "No CGPA cut-off stated in the posting.", c, candidate=cgpa_str)
        elif c.value is None:
            checks["cgpa"] = _check("UNKNOWN", "Posting states a percentage cut-off; compare it with your marks manually.", c,
                                    requirement="percentage cut-off", candidate=cgpa_str)
        elif cand_cgpa is None:
            checks["cgpa"] = _check("UNKNOWN", f"Posting requires CGPA >= {c.value}, but your CGPA is missing from your profile.", c,
                                    requirement=f">= {c.value}")
        elif cand_cgpa >= c.value:
            checks["cgpa"] = _check("PASS", f"Your CGPA {cand_cgpa} meets the cut-off of {c.value}.", c, requirement=f">= {c.value}", candidate=cgpa_str)
        else:
            checks["cgpa"] = _check("FAIL", f"Your CGPA {cand_cgpa} is below the cut-off of {c.value}.", c, requirement=f">= {c.value}", candidate=cgpa_str)

        # 4. Active backlogs -------------------------------------------------------------
        b = req.max_backlogs
        bl_str = None if cand_backlogs is None else str(cand_backlogs)
        if b.value is None:
            checks["backlogs"] = _check("PASS", "No backlog rule stated in the posting.", b, candidate=bl_str)
        elif cand_backlogs is None:
            rule = "no active backlogs" if b.value == 0 else f"at most {b.value} active backlog(s)"
            checks["backlogs"] = _check("UNKNOWN", f"Posting requires {rule}; add your backlog count to your profile.", b,
                                        requirement=f"<= {b.value}")
        elif cand_backlogs <= b.value:
            checks["backlogs"] = _check("PASS", f"You have {cand_backlogs} active backlog(s); the posting allows {b.value}.", b,
                                        requirement=f"<= {b.value}", candidate=bl_str)
        else:
            checks["backlogs"] = _check("FAIL", f"You have {cand_backlogs} active backlog(s); the posting allows {b.value}.", b,
                                        requirement=f"<= {b.value}", candidate=bl_str)

        # 5. Experience level ------------------------------------------------------------
        lvl, yrs = req.level, req.experience_years
        if lvl.value == "senior":
            checks["experience_level"] = _check("FAIL", "Senior/lead-level role; you are looking for intern/fresher roles.", lvl)
        elif yrs.value is not None and yrs.value >= 2:
            checks["experience_level"] = _check("FAIL", f"Requires {yrs.value}+ years of experience; you are a student seeking intern/fresher roles.",
                                                yrs, requirement=f"{yrs.value}+ years")
        elif yrs.value == 1:
            checks["experience_level"] = _check("UNKNOWN", "Asks for about 1 year of experience; check whether internships count.", yrs,
                                                requirement="1 year")
        elif lvl.value == "intern/fresher":
            checks["experience_level"] = _check("PASS", "Role is for interns / freshers / entry level.", lvl)
        else:
            checks["experience_level"] = _check("UNKNOWN", "Experience level is not stated (not marked intern/fresher/entry-level, no years given).", lvl)

        # 6. Skills (advisory: shown, never decides eligibility on its own) -----------------
        job_skills = job.required_skills or []
        have = {s.lower() for s in (candidate_skills or [])}
        if not job_skills:
            checks["skills"] = _check("UNKNOWN", "No recognisable skills listed in the posting text.", hard=False)
        else:
            matched = [s for s in job_skills if s.lower() in have]
            ratio = len(matched) / len(job_skills)
            status = "PASS" if ratio >= 0.5 else ("UNKNOWN" if matched else "FAIL")
            checks["skills"] = _check(status, f"You have {len(matched)} of {len(job_skills)} listed skills"
                                      + (f" ({', '.join(matched[:6])})." if matched else "."),
                                      requirement=", ".join(job_skills[:10]), candidate=", ".join(matched[:10]) or None, hard=False)

        # 7. Location ------------------------------------------------------------------------
        category, loc_detail = classify_location(job.location or "", job.work_mode or "")
        loc_req = Requirement(job.location, "inferred" if job.location else "missing",
                              f"Listing location: {job.location}" if job.location else None)
        if category == "india":
            checks["location"] = _check("PASS", f"Location '{job.location}' is in India (or remote open to India).", loc_req)
        elif category == "open_remote":
            checks["location"] = _check("PASS", f"Remote with no country restriction stated ('{job.location or 'not stated'}').", loc_req)
        elif category == "restricted_remote":
            checks["location"] = _check("FAIL", f"Remote, but limited to another region ('{loc_detail}'). Not open to candidates in India.", loc_req)
        elif category == "remote_region_unclear":
            checks["location"] = _check("UNKNOWN", f"Marked remote, but lists '{job.location}'. Check whether applicants from India are accepted.", loc_req)
        elif category == "unknown":
            checks["location"] = _check("UNKNOWN", "Job location is not stated.", loc_req)
        else:
            checks["location"] = _check("FAIL", f"Onsite/hybrid abroad ('{job.location}'). International roles must be remote and open to India.", loc_req)

        # 8. Work mode -------------------------------------------------------------------------
        mode = (job.work_mode or "Unknown").lower()
        mode_req = Requirement(job.work_mode, "inferred" if mode != "unknown" else "missing",
                               f"Listing work mode: {job.work_mode}" if mode != "unknown" else None)
        if preferred_work_mode in ("any", ""):
            checks["work_mode"] = _check("PASS", f"Work mode '{job.work_mode or 'Unknown'}' is fine: you accept any mode.", mode_req, candidate="Any")
        elif mode == "unknown":
            checks["work_mode"] = _check("UNKNOWN", f"Work mode not stated; you prefer {profile.work_mode}.", mode_req, candidate=profile.work_mode)
        elif mode == preferred_work_mode or (preferred_work_mode == "hybrid" and mode == "remote"):
            checks["work_mode"] = _check("PASS", f"{job.work_mode} matches your preference ({profile.work_mode}).", mode_req, candidate=profile.work_mode)
        else:
            checks["work_mode"] = _check("FAIL", f"{job.work_mode} role; you prefer {profile.work_mode} only.", mode_req, candidate=profile.work_mode)

        # 9. Work authorisation ---------------------------------------------------------------
        wa, ns = req.work_authorization, req.no_sponsorship
        countries_str = ", ".join(c.title() for c in cand_countries) or None
        if wa.value is None and not ns.value:
            checks["work_authorization"] = _check("PASS", "No work-authorisation rule stated in the posting.", wa, candidate=countries_str)
        elif wa.value is None:
            # "no sponsorship" only matters if the job is outside the countries you can work in
            if category == "india" and "india" in cand_countries:
                checks["work_authorization"] = _check("PASS", "Posting offers no visa sponsorship; not needed for a role in India.", ns,
                                                      requirement="no sponsorship", candidate=countries_str)
            else:
                checks["work_authorization"] = _check("UNKNOWN", "Posting offers no visa sponsorship. Check that you can work for them from India.", ns,
                                                      requirement="no sponsorship", candidate=countries_str)
        elif not cand_countries:
            checks["work_authorization"] = _check("UNKNOWN", f"Posting requires authorisation to work in {wa.value}; add your work authorisation to your profile.", wa)
        elif wa.value.lower() in cand_countries:
            checks["work_authorization"] = _check("PASS", f"You are authorised to work in {wa.value}.", wa, candidate=countries_str)
        else:
            checks["work_authorization"] = _check("FAIL", f"Requires authorisation to work in {wa.value}; your profile lists {countries_str}.",
                                                  wa, candidate=countries_str)

        # 10. Other hard requirements ------------------------------------------------------------
        others = []
        if req.relocation.value:
            others.append(("relocation", req.relocation))
        if req.full_time_required.value:
            others.append(("full-time availability", req.full_time_required))
        if others:
            names = " and ".join(n for n, _ in others)
            checks["other"] = _check("UNKNOWN", f"Posting requires {names}. Confirm this works with your studies.", others[0][1], requirement=names)
        elif req.internship_duration.value:
            checks["other"] = _check("PASS", f"Internship duration stated: {req.internship_duration.value} (for your information).",
                                     req.internship_duration, hard=False)
        else:
            checks["other"] = _check("PASS", "No other hard requirements detected.", hard=False)

        for key, chk in checks.items():
            chk.label = CHECK_LABELS[key]

        hard = [c for c in checks.values() if c.hard]
        if any(c.status == "FAIL" for c in hard):
            overall = "FAIL"
        elif any(c.status == "UNKNOWN" for c in hard):
            overall = "UNKNOWN"
        else:
            overall = "PASS"

        return EligibilityResponse(
            job_id=job.id,
            overall_status=overall,
            degree=checks["degree"],
            graduation=checks["graduation"],
            cgpa=checks["cgpa"],
            location=checks["location"],
            work_mode=checks["work_mode"],
            experience_level=checks["experience_level"],
            checks=checks,
            rejection_reasons=[c.details for c in hard if c.status == "FAIL"],
            unverified_requirements=[c.details for c in hard if c.status == "UNKNOWN"],
        )
