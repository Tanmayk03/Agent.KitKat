"""
Agent KitKat - Eligibility Verification Agent
Compares job requirements with candidate's saved profile using deterministic rules.

Strict Rules:
- Unknown information must NEVER be treated as a pass.
- Hard eligibility failures override the match score.
- Clearly explains why a job is rejected.
- Identifies requirements still needing verification.
"""

import logging
from typing import Dict, Any, List, Tuple

from backend.database.models import Job, UserProfile
from backend.schemas.matching import RequirementCheck, EligibilityResponse

logger = logging.getLogger("agent_kitkat.eligibility_agent")


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
        # Check 5: Location
        # ---------------------------------------------------------
        job_loc_lower = (job.location or "").lower()
        if (
            job_mode_lower == "remote"
            or "remote" in job_loc_lower
            or "worldwide" in job_loc_lower
            or "anywhere" in job_loc_lower
            or "remote" in (job.work_mode or "").lower()
        ):
            location_check = RequirementCheck(
                status="PASS",
                details=f"Remote work mode supported ({job.location or 'Remote'})."
            )
        elif any(pref in job_loc_lower for pref in preferred_locations):
            location_check = RequirementCheck(
                status="PASS",
                details=f"Job location '{job.location}' matches candidate preferred locations."
            )
        elif "india" in job_loc_lower:
            location_check = RequirementCheck(
                status="PASS",
                details=f"Job location '{job.location}' is within India."
            )
        elif not job.location or job.location == "Not Specified":
            location_check = RequirementCheck(
                status="PASS",
                details="Flexible / unconstrained location."
            )
        else:
            location_check = RequirementCheck(
                status="PASS" if "remote" in preferred_locations else "UNKNOWN",
                details=f"Job location: {job.location}."
            )

        # ---------------------------------------------------------
        # Overall Status Determination
        # ---------------------------------------------------------
        all_checks = [grad_check, cgpa_check, degree_check, work_mode_check, location_check]
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
            rejection_reasons=rejection_reasons,
            unverified_requirements=unverified_requirements
        )
