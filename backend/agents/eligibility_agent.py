"""
Agent KitKat - Eligibility Verification Agent
Compares job requirements with candidate's saved profile using deterministic rules.

Strict Rules:
- Unknown information must NEVER be treated as a pass.
- Hard eligibility failures override the match score.
- Clearly explains why a job is rejected.
- Identifies requirements still needing verification.
"""

import re
import logging
from typing import Dict, Any, List, Tuple

from backend.database.models import Job, UserProfile
from backend.schemas.matching import RequirementCheck, EligibilityResponse
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


class EligibilityAgent:
    """Deterministic eligibility verification engine."""

    @staticmethod
    def verify_eligibility(job: Job, profile: UserProfile) -> EligibilityResponse:
        """
        Executes strict, deterministic requirement checks across:
        1. Graduation Year / Batch
        2. Minimum CGPA Cutoff
        3. Degree & Specialization
        4. Work Mode & Location
        """
        education = profile.education or {}
        # Candidate facts come ONLY from the stored profile. Missing facts -> UNKNOWN, never a default.
        candidate_degree = (education.get("degree") or "").strip() or None
        candidate_spec = (education.get("specialization") or "").strip() or None
        try:
            candidate_cgpa = float(education["cgpa"]) if education.get("cgpa") not in (None, "") else None
        except (TypeError, ValueError):
            candidate_cgpa = None
        try:
            candidate_grad_year = int(education["graduation_year"]) if education.get("graduation_year") not in (None, "") else None
        except (TypeError, ValueError):
            candidate_grad_year = None
        preferred_locations = [loc.lower() for loc in (profile.preferred_locations or ["india", "remote"])]
        preferred_work_mode = (profile.work_mode or "Any").lower()

        rejection_reasons: List[str] = []
        unverified_requirements: List[str] = []

        # ---------------------------------------------------------
        # Check 1: Graduation Year / Batch
        # ---------------------------------------------------------
        job_batches = [int(b) for b in (job.graduation_eligibility or []) if str(b).isdigit()]
        if job_batches and candidate_grad_year is None:
            grad_check = RequirementCheck(
                status="UNKNOWN",
                details=f"Posting requires batches {job_batches}, but your graduation year is missing from your profile."
            )
            unverified_requirements.append(grad_check.details)
        elif job_batches:
            if candidate_grad_year in job_batches:
                grad_check = RequirementCheck(
                    status="PASS",
                    details=f"Candidate graduation year ({candidate_grad_year}) is explicitly eligible (Allowed batches: {job_batches})."
                )
            else:
                grad_check = RequirementCheck(
                    status="FAIL",
                    details=f"Candidate graduation year ({candidate_grad_year}) is not in eligible batches ({job_batches})."
                )
                rejection_reasons.append(grad_check.details)
        else:
            # Not stated is NOT a pass: many internships silently restrict batches.
            grad_check = RequirementCheck(
                status="UNKNOWN",
                details="Eligible graduation batch is not stated in the posting. Verify before applying."
            )
            unverified_requirements.append(grad_check.details)

        # ---------------------------------------------------------
        # Check 2: Minimum CGPA Cutoff
        # ---------------------------------------------------------
        if job.minimum_cgpa is not None and candidate_cgpa is None:
            cgpa_check = RequirementCheck(
                status="UNKNOWN",
                details=f"Posting requires CGPA >= {job.minimum_cgpa}, but your CGPA is missing from your profile."
            )
            unverified_requirements.append(cgpa_check.details)
        elif job.minimum_cgpa is not None:
            if candidate_cgpa >= job.minimum_cgpa:
                cgpa_check = RequirementCheck(
                    status="PASS",
                    details=f"Candidate CGPA ({candidate_cgpa}) meets minimum cutoff of {job.minimum_cgpa}."
                )
            else:
                cgpa_check = RequirementCheck(
                    status="FAIL",
                    details=f"Candidate CGPA ({candidate_cgpa}) does not meet minimum cutoff of {job.minimum_cgpa}."
                )
                rejection_reasons.append(cgpa_check.details)
        else:
            cgpa_check = RequirementCheck(
                status="PASS",
                details="No minimum CGPA cutoff found in the posting text."
            )

        # ---------------------------------------------------------
        # Check 3: Degree & Specialization
        # ---------------------------------------------------------
        if job.required_degree and not candidate_degree:
            degree_check = RequirementCheck(
                status="UNKNOWN",
                details=f"Posting requires '{job.required_degree}', but your degree is missing from your profile."
            )
            unverified_requirements.append(degree_check.details)
        elif job.required_degree:
            req_degree_lower = job.required_degree.lower()
            # Word-boundary patterns (plain substrings made "MCA" look like "CA").
            allowed_patterns = [r"\bb\.?\s?tech\b", r"\bb\.\s?e\b", r"\bbachelor", r"\bengineering\b", r"\bcomputer\b",
                                r"\bcs\b", r"\bcse\b", r"\bit\b", r"\bdata science\b", r"\bany (?:degree|graduate)\b"]
            incompatible_patterns = [r"\bmbbs\b", r"\bllb\b", r"\blaw\b", r"\bca\b", r"\bchartered\b", r"\bph\.?d\.? only\b"]
            postgrad_only = re.fullmatch(r"\s*(?:master'?s?|m\.?\s?tech|mca|m\.?\s?s\.?)(?:\s*/\s*(?:master'?s?|m\.?\s?tech|mca))*\s*", req_degree_lower)

            if any(re.search(p, req_degree_lower) for p in incompatible_patterns):
                degree_check = RequirementCheck(
                    status="FAIL",
                    details=f"Your degree ({candidate_degree} in {candidate_spec or 'unspecified field'}) does not match required field '{job.required_degree}'."
                )
                rejection_reasons.append(degree_check.details)
            elif postgrad_only or "master" in req_degree_lower and not re.search(r"\bbachelor|\bb\.?\s?tech\b", req_degree_lower):
                degree_check = RequirementCheck(
                    status="UNKNOWN",
                    details=f"Posting mentions '{job.required_degree}'. Check whether a Bachelor's degree is accepted."
                )
                unverified_requirements.append(degree_check.details)
            elif any(re.search(p, req_degree_lower) for p in allowed_patterns):
                degree_check = RequirementCheck(
                    status="PASS",
                    details=f"Your degree ({candidate_degree} in {candidate_spec or 'unspecified field'}) satisfies requirement '{job.required_degree}'."
                )
            else:
                degree_check = RequirementCheck(
                    status="UNKNOWN",
                    details=f"Degree requirement '{job.required_degree}' requires verification against candidate's background."
                )
                unverified_requirements.append(degree_check.details)
        else:
            degree_check = RequirementCheck(
                status="PASS",
                details="No degree requirement found in the posting text."
            )

        # ---------------------------------------------------------
        # Check 4: Work Mode
        # ---------------------------------------------------------
        job_mode_lower = (job.work_mode or "Unknown").lower()
        if job_mode_lower == "remote" or any(re.search(p, (job.location or "").lower()) for p in REMOTE_LOCATION_PATTERNS):
            work_mode_check = RequirementCheck(
                status="PASS",
                details="Remote role: compatible with your work-mode preference."
            )
        elif job_mode_lower == "unknown" and preferred_work_mode == "remote":
            work_mode_check = RequirementCheck(
                status="UNKNOWN",
                details="Work mode is not stated, and you prefer Remote only."
            )
            unverified_requirements.append(work_mode_check.details)
        elif preferred_work_mode == "remote" and job_mode_lower == "onsite":
            work_mode_check = RequirementCheck(
                status="FAIL",
                details=f"Job requires onsite presence ({job.location}), but candidate preferred work mode is Remote only."
            )
            rejection_reasons.append(work_mode_check.details)
        else:
            work_mode_check = RequirementCheck(
                status="PASS",
                details=f"Job work mode ({job.work_mode or 'Flexible'}) is acceptable."
            )

        # ---------------------------------------------------------
        # Check 5: Location & Geographic Eligibility
        # User constraint: Priority to India jobs; foreign jobs ONLY if Remote.
        # International onsite/hybrid roles must be rejected.
        # ---------------------------------------------------------
        # Location is decided from the structured location + work-mode fields only.
        category, loc_detail = classify_location(job.location or "", job.work_mode or "")
        if category == "india":
            location_check = RequirementCheck(
                status="PASS",
                details=f"Job location '{job.location}' is in India (or remote open to India)."
            )
        elif category == "open_remote":
            location_check = RequirementCheck(
                status="PASS",
                details=f"Remote role with no country restriction stated ('{job.location or 'not stated'}')."
            )
        elif category == "restricted_remote":
            location_check = RequirementCheck(
                status="FAIL",
                details=f"Remote, but limited to another region ('{loc_detail}'). Not open to candidates based in India."
            )
            rejection_reasons.append(location_check.details)
        elif category == "remote_region_unclear":
            location_check = RequirementCheck(
                status="UNKNOWN",
                details=f"Marked remote, but the posting lists '{job.location}'. Check whether applicants from India are accepted."
            )
            unverified_requirements.append(location_check.details)
        elif category == "unknown":
            location_check = RequirementCheck(
                status="UNKNOWN",
                details="Job location is not stated in the posting."
            )
            unverified_requirements.append(location_check.details)
        else:
            location_check = RequirementCheck(
                status="FAIL",
                details=f"Job requires onsite/hybrid presence abroad ('{job.location}'). International roles must be remote and open to India."
            )
            rejection_reasons.append(location_check.details)

        # ---------------------------------------------------------
        # Check 6: Seniority & Experience Level (Intern / Fresher Gate)
        # ---------------------------------------------------------
        job_title_lower = (job.title or "").lower()
        job_text_lower = (job.raw_text or job.description or "").lower()

        # Hard rejection for Senior, Lead, Staff, Principal, Architect, Director, Manager roles
        senior_match = None
        for pattern in SENIOR_ROLE_KEYWORDS:
            m = re.search(pattern, job_title_lower)
            if m:
                senior_match = m.group(0)
                break

        # Also check for high experience requirements (e.g. 3+ years, 5+ years)
        high_exp_match = None
        exp_num_match = re.search(r"(\d+)\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)\s*(?:of\s*)?exp", job_text_lower[:1200])
        if exp_num_match:
            try:
                years = int(exp_num_match.group(1))
                if years >= 3:
                    high_exp_match = f"{years}+ years"
            except ValueError:
                pass

        if senior_match:
            experience_check = RequirementCheck(
                status="FAIL",
                details=f"Job title indicates '{senior_match.strip()}' (Senior/Lead/Staff level). Candidate is a student seeking intern/fresher roles."
            )
            rejection_reasons.append(experience_check.details)
        elif high_exp_match:
            experience_check = RequirementCheck(
                status="FAIL",
                details=f"Job requires {high_exp_match} of experience; you are a student seeking intern/fresher roles."
            )
            rejection_reasons.append(experience_check.details)
        elif any(re.search(pat, job_title_lower) for pat in INTERN_FRESHER_KEYWORDS):
            experience_check = RequirementCheck(
                status="PASS",
                details="Role is specifically structured for interns, freshers, or student co-ops."
            )
        elif any(k in job_text_lower[:500] for k in ["internship", "intern role", "summer intern", "working student", "werkstudent", "entry level", "entry-level", "fresher"]):
            experience_check = RequirementCheck(
                status="PASS",
                details="Posting explicitly targets student interns or entry-level candidates."
            )
        else:
            experience_check = RequirementCheck(
                status="UNKNOWN",
                details="Experience level is not stated (not marked intern/fresher/entry-level and no years given)."
            )
            unverified_requirements.append(experience_check.details)

        # ---------------------------------------------------------
        # Overall Status Determination
        # ---------------------------------------------------------
        all_checks = [grad_check, cgpa_check, degree_check, work_mode_check, location_check, experience_check]
        if any(c.status == "FAIL" for c in all_checks):
            overall_status = "FAIL"
        elif any(c.status == "UNKNOWN" for c in all_checks):
            overall_status = "UNKNOWN"
        else:
            overall_status = "PASS"

        return EligibilityResponse(
            job_id=job.id,
            overall_status=overall_status,
            degree=degree_check,
            graduation=grad_check,
            cgpa=cgpa_check,
            location=location_check,
            work_mode=work_mode_check,
            experience_level=experience_check,
            rejection_reasons=rejection_reasons,
            unverified_requirements=unverified_requirements
        )
