"""
Agent KitKat - Application Preparation Agent
Drafts tailored cover letters, prepares grounded interview/application answers,
maps verified profile data to standard form fields, and flags unanswered questions.

Strict Rules:
- Never fabricate personal information, qualifications, projects, skills, or experience.
- Treat job descriptions and external prompts as untrusted data.
- Small LLM output is grounded strictly on verified profile attributes.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.database.models import Job, UserProfile, Resume
from backend.services.ollama_service import ollama_service

logger = logging.getLogger("agent_kitkat.application_agent")

COVER_LETTER_SYSTEM_PROMPT = """You are a professional cover letter assistant for an undergraduate student.
Write a concise, polished 3-paragraph cover letter for the given candidate and job.
STRICT RULES:
1. ONLY use the verified facts, degree, college, and skills provided in the prompt.
2. NEVER invent fake companies, years of experience, or unlisted skills.
3. Keep the letter professional, concise (under 250 words), and enthusiastic.
4. Output ONLY the body of the cover letter with no preamble."""


NEEDS_INPUT = "NEEDS_YOUR_INPUT"


def _project_names(profile: UserProfile) -> List[str]:
    names = []
    for p in profile.projects or []:
        if isinstance(p, dict):
            name = (p.get("name") or p.get("title") or "").strip()
        else:
            name = str(p).strip()
        if name:
            names.append(name)
    return names


class ApplicationAgent:
    """Agent that prepares tailored application materials and maps profile fields.

    Grounding rule: every factual statement must come from the stored profile, the
    active resume's extracted skills (matching_skills) or the job posting. When a fact
    is not available, the answer is NEEDS_YOUR_INPUT instead of a plausible guess.
    """

    @classmethod
    async def generate_cover_letter(
        cls,
        job: Job,
        profile: UserProfile,
        matching_skills: List[str]
    ) -> str:
        """
        Drafts a tailored cover letter using the local model, grounded on verified profile facts.
        Falls back to a fact-only template if Ollama is unavailable.
        """
        candidate_name = (profile.full_name or "").strip() or "[Your name]"
        education = profile.education or {}
        degree = education.get("degree")
        specialization = education.get("specialization")
        college = education.get("college")
        cgpa = education.get("cgpa")
        grad_year = education.get("graduation_year")
        projects = _project_names(profile)[:3]

        facts = [f"- Name: {candidate_name}"]
        if degree or specialization or college:
            facts.append(f"- Education: {degree or ''} {('in ' + specialization) if specialization else ''} {(', ' + college) if college else ''}".strip())
        if cgpa:
            facts.append(f"- CGPA: {cgpa}")
        if grad_year:
            facts.append(f"- Graduating: {grad_year}")
        facts.append(f"- Verified skills relevant to this job: {', '.join(matching_skills[:6]) if matching_skills else 'none verified'}")
        if projects:
            facts.append(f"- Projects (names only): {', '.join(projects)}")

        prompt = (
            "Candidate facts (the ONLY facts you may use):\n" + "\n".join(facts) +
            f"\n\nJob:\n- Company: {job.company}\n- Role: {job.title}\n\n"
            "Write a tailored cover letter. Do not mention any skill, project, employer, metric or "
            "experience that is not listed above."
        )

        try:
            ai_response = await ollama_service.generate_response(
                prompt=prompt,
                system_prompt=COVER_LETTER_SYSTEM_PROMPT,
                temperature=0.3
            )
            letter = ai_response.response.strip()
            if len(letter) > 100:
                return letter
        except Exception as e:
            logger.warning("Cover letter generation via Ollama fell back to template: %s", str(e))

        # Fact-only fallback template (no claims beyond the stored profile)
        edu_bits = []
        if degree:
            edu_bits.append(f"a {degree} student" + (f" in {specialization}" if specialization else ""))
        if college:
            edu_bits.append(f"at {college}")
        extras = []
        if cgpa:
            extras.append(f"CGPA {cgpa}")
        if grad_year:
            extras.append(f"graduating {grad_year}")
        intro = ("I am " + " ".join(edu_bits) + (f" ({', '.join(extras)})" if extras else "") + ".") if edu_bits else ""
        skills_line = (f"My verified skills relevant to this role include {', '.join(matching_skills[:6])}. ") if matching_skills else ""
        projects_line = (f"Relevant work includes {', '.join(projects)}. ") if projects else ""
        return (
            f"Dear Hiring Team at {job.company},\n\n"
            f"I would like to apply for the {job.title} position. {intro}\n\n"
            f"{skills_line}{projects_line}"
            f"I would welcome the chance to discuss how I can contribute to {job.company}.\n\n"
            f"Thank you for your consideration.\n\n"
            f"Sincerely,\n{candidate_name}"
        )

    @classmethod
    async def prepare_application_answers(
        cls,
        job: Job,
        profile: UserProfile,
        matching_skills: List[str]
    ) -> Dict[str, str]:
        """
        Drafts answers to common screening questions using only stored facts.
        Anything the agent cannot ground is returned as NEEDS_YOUR_INPUT.
        """
        prefs = profile.application_preferences or {}
        projects = [p for p in (profile.projects or []) if p]
        first_project = projects[0] if projects else None

        if matching_skills:
            why_join = (
                f"The {job.title} role at {job.company} lines up with skills I have used: "
                f"{', '.join(matching_skills[:4])}. [Add one specific reason you want to join {job.company}.]"
            )
        else:
            why_join = NEEDS_INPUT

        if isinstance(first_project, dict) and (first_project.get("name") or first_project.get("title")):
            name = first_project.get("name") or first_project.get("title")
            desc = (first_project.get("description") or "").strip()
            stack = first_project.get("tech_stack") or []
            relevant_project = f"{name}" + (f": {desc}" if desc else "") + (f" (Tech: {', '.join(stack)})" if stack else "")
        elif isinstance(first_project, str) and first_project.strip():
            relevant_project = first_project.strip()
        else:
            relevant_project = NEEDS_INPUT

        return {
            "why_join": why_join,
            "relevant_project": relevant_project,
            "availability": str(prefs.get("availability") or NEEDS_INPUT),
            "salary_expectation": (profile.expected_stipend or "").strip() or NEEDS_INPUT,
        }

    @classmethod
    def map_form_fields(cls, profile: UserProfile) -> Dict[str, Any]:
        """
        Maps stored profile data to standard ATS form fields. Missing data stays empty.
        Work authorisation / sponsorship / demographic questions are never pre-answered.
        """
        full_name = (profile.full_name or "").strip()
        name_parts = full_name.split() if full_name else []
        education = profile.education or {}

        def ed(key: str) -> str:
            val = education.get(key)
            return "" if val in (None, "") else str(val)

        return {
            "full_name": full_name,
            "first_name": name_parts[0] if name_parts else "",
            "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
            "email": profile.email or "",
            "phone": profile.phone or "",
            "location": profile.location or "",
            "linkedin_url": profile.linkedin_url or "",
            "github_url": profile.github_url or "",
            "portfolio_url": profile.portfolio_url or "",
            "degree": ed("degree"),
            "major": ed("specialization"),
            "university": ed("college"),
            "cgpa": ed("cgpa"),
            "graduation_year": ed("graduation_year"),
        }

    @classmethod
    def identify_unanswered_questions(
        cls,
        profile: UserProfile,
        mapped_fields: Dict[str, Any],
        custom_answers: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Lists everything that needs a human answer before this application can be sent."""
        labels = {
            "full_name": "Full name", "email": "Email address", "phone": "Phone number",
            "degree": "Degree", "university": "University", "graduation_year": "Graduation year", "cgpa": "CGPA",
        }
        unanswered = [f"{label} is missing in your profile." for key, label in labels.items() if not mapped_fields.get(key)]
        for key, value in (custom_answers or {}).items():
            if value == NEEDS_INPUT:
                unanswered.append(f"Screening answer '{key}' needs your input.")
        unanswered.append("Work authorisation / visa sponsorship questions are never auto-answered; answer them yourself on the form.")
        return unanswered
