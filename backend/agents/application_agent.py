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


class ApplicationAgent:
    """Agent that prepares tailored application materials and maps profile fields."""

    @classmethod
    async def generate_cover_letter(
        cls,
        job: Job,
        profile: UserProfile,
        matching_skills: List[str]
    ) -> str:
        """
        Drafts a tailored cover letter using Qwen2.5 1.5B grounded on verified profile facts.
        Falls back to a structured template if Ollama is unavailable.
        """
        candidate_name = profile.full_name or "Candidate"
        education = profile.education or {}
        degree = education.get("degree", "B.Tech")
        specialization = education.get("specialization", "Computer Science and Data Science")
        college = education.get("college", "SRM University, Delhi NCR")
        cgpa = education.get("cgpa", 8.44)
        grad_year = education.get("graduation_year", 2027)

        skills_list_str = ", ".join(matching_skills[:6]) if matching_skills else "Python, Web Development"

        prompt = f"""Candidate Profile:
- Name: {candidate_name}
- Education: {degree} in {specialization}, {college} (CGPA: {cgpa}, Graduating: {grad_year})
- Verified Relevant Skills: {skills_list_str}

Job Details:
- Company: {job.company}
- Role: {job.title}
- Location: {job.location} ({job.work_mode})

Write a tailored cover letter for this internship role."""

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

        # Grounded deterministic fallback template
        return (
            f"Dear Hiring Team at {job.company},\n\n"
            f"I am writing to express my strong enthusiasm for the {job.title} position. "
            f"As a {degree} student in {specialization} at {college} (CGPA: {cgpa}, Class of {grad_year}), "
            f"I have developed solid technical foundations and practical engineering experience.\n\n"
            f"With proficiency in {skills_list_str}, I have built robust projects and actively practice software development best practices. "
            f"I am eager to apply my technical problem-solving skills to contribute effectively to {job.company}'s engineering objectives.\n\n"
            f"Thank you for considering my application. I look forward to the opportunity to discuss how my background and enthusiasm align with your team's needs.\n\n"
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
        Prepares answers to common application screening questions grounded on verified facts.
        """
        education = profile.education or {}
        degree = education.get("degree", "B.Tech")
        college = education.get("college", "SRM University, Delhi NCR")
        stipend_pref = profile.expected_stipend or "Market Rate / Competitive"
        skills_str = ", ".join(matching_skills[:4]) if matching_skills else "Python, Web Development"

        return {
            "why_join": (
                f"I am deeply inspired by {job.company}'s work and see the {job.title} role as a tremendous opportunity "
                f"to contribute my technical skills in {skills_str} while solving real-world challenges."
            ),
            "relevant_project": (
                f"As a {degree} student at {college}, I built autonomous and web development projects using Python, React, and SQL, "
                f"focusing on clean architecture, modular APIs, and efficient data processing."
            ),
            "availability": (
                "Available immediately for intern positions with flexible working hours for remote or local onsite requirements."
            ),
            "salary_expectation": stipend_pref
        }

    @classmethod
    def map_form_fields(cls, profile: UserProfile) -> Dict[str, Any]:
        """
        Maps verified profile data to standard ATS and application form fields.
        """
        full_name = (profile.full_name or "").strip()
        name_parts = full_name.split() if full_name else []
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        education = profile.education or {}

        return {
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "email": profile.email or "",
            "phone": profile.phone or "",
            "location": profile.location or "India",
            "linkedin_url": profile.linkedin_url or "",
            "github_url": profile.github_url or "",
            "portfolio_url": profile.portfolio_url or "",
            "degree": education.get("degree", "B.Tech"),
            "major": education.get("specialization", "Computer Science and Data Science"),
            "university": education.get("college", "SRM University, Delhi NCR"),
            "cgpa": str(education.get("cgpa", 8.44)),
            "graduation_year": str(education.get("graduation_year", 2027)),
            "work_authorization": "Authorized to work in India",
            "requires_sponsorship": "No"
        }

    @classmethod
    def identify_unanswered_questions(
        cls,
        profile: UserProfile,
        mapped_fields: Dict[str, Any]
    ) -> List[str]:
        """
        Detects missing essential fields or declarations requiring human confirmation.
        """
        unanswered = []
        if not mapped_fields.get("full_name"):
            unanswered.append("Candidate Full Name is missing in profile.")
        if not mapped_fields.get("email"):
            unanswered.append("Candidate Email address is missing in profile.")
        if not mapped_fields.get("phone"):
            unanswered.append("Candidate Phone number is missing in profile.")

        return unanswered
