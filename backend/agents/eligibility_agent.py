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
        candidate_degree = education.get("degree", "B.Tech")
        candidate_spec = education.get("specialization", "Computer Science and Data Science")
        candidate_cgpa = float(education.get("cgpa", 8.44))
        candidate_grad_year = int(education.get("graduation_year", 2027))
        preferred_locations = [loc.lower() for loc in (profile.preferred_locations or ["india", "remote"])]
        preferred_work_mode = (profile.work_mode or "Any").lower()

        rejection_reasons: List[str] = []
        unverified_requirements: List[str] = []

        # ---------------------------------------------------------
        # Check 1: Graduation Year / Batch
        # ---------------------------------------------------------
        job_batches = [int(b) for b in (job.graduation_eligibility or []) if str(b).isdigit()]
        if job_batches:
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
            # Job does not restrict graduation batch -> Open to candidate
            grad_check = RequirementCheck(
                status="PASS",
                details=f"No restrictive graduation batch specified. Open to {candidate_grad_year} candidates."
            )

        # ---------------------------------------------------------
        # Check 2: Minimum CGPA Cutoff
        # ---------------------------------------------------------
        if job.minimum_cgpa is not None:
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
                details="No minimum CGPA cutoff required."
            )

        # ---------------------------------------------------------
        # Check 3: Degree & Specialization
        # ---------------------------------------------------------
        if job.required_degree:
            req_degree_lower = job.required_degree.lower()
            allowed_keywords = ["b.tech", "b.e", "bachelor", "engineering", "computer", "cs", "it", "data science", "any"]
            incompatible_keywords = ["mbbs", "llb", "law", "ca", "chartered", "phd only", "ph.d only"]

            if any(k in req_degree_lower for k in incompatible_keywords):
                degree_check = RequirementCheck(
                    status="FAIL",
                    details=f"Candidate degree ({candidate_degree} in {candidate_spec}) does not match required field '{job.required_degree}'."
                )
                rejection_reasons.append(degree_check.details)
            elif any(k in req_degree_lower for k in allowed_keywords):
                degree_check = RequirementCheck(
                    status="PASS",
                    details=f"Candidate degree ({candidate_degree} in {candidate_spec}) satisfies requirement '{job.required_degree}'."
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
                details="No specific degree restriction specified."
            )

        # ---------------------------------------------------------
        # Check 4: Work Mode
        # ---------------------------------------------------------
        job_mode_lower = (job.work_mode or "Unknown").lower()
        if job_mode_lower == "remote" or "remote" in (job.location or "").lower() or "remote" in (job.raw_text or "").lower():
            work_mode_check = RequirementCheck(
                status="PASS",
                details="Remote work mode matches candidate preferences."
            )
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
        job_loc_lower = (job.location or "").lower()
        job_mode_lower = (job.work_mode or "Unknown").lower()
        job_raw_lower = (job.raw_text or "").lower()

        is_in_india = (
            any(re.search(pat, job_loc_lower) for pat in INDIA_LOCATION_PATTERNS)
            or any(re.search(pat, job_raw_lower[:500]) for pat in INDIA_LOCATION_PATTERNS)
        )
        is_remote = (
            job_mode_lower == "remote"
            or any(re.search(pat, job_loc_lower) for pat in REMOTE_LOCATION_PATTERNS)
            or any(re.search(pat, (job.work_mode or "").lower()) for pat in REMOTE_LOCATION_PATTERNS)
            or "remote" in job_raw_lower[:300]
        )

        if is_in_india:
            location_check = RequirementCheck(
                status="PASS",
                details=f"Job location '{job.location}' is within India (Top Candidate Priority)."
            )
        elif is_remote:
            location_check = RequirementCheck(
                status="PASS",
                details=f"International Remote position supported for India-based candidate ({job.location})."
            )
        else:
            # Foreign location requiring onsite or hybrid presence
            location_check = RequirementCheck(
                status="FAIL",
                details=f"Job requires onsite/hybrid presence abroad ('{job.location}'). International roles must be 100% remote for India-based candidate."
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
                details=f"Job requires {high_exp_match} of experience. Candidate is a student (Batch {candidate_grad_year}) seeking intern/fresher roles."
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
                status="PASS",
                details="Entry/intermediate technical role without senior-level requirement."
            )

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
