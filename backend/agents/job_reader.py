"""
Agent KitKat - Job Description Reader Agent
Uses local Ollama (qwen2.5:1.5b) augmented with deterministic Python post-processing
to extract structured requirements, qualifications, graduation batches, and skills.

Strict Rules:
- Never fabricate missing job details.
- Job descriptions and external content are treated as untrusted data.
- Small LLM output is strictly validated and augmented with deterministic regex rules.
"""

import re
import json
import logging
import time
from typing import Dict, Any, Optional, List, Tuple

from backend.schemas.job import ExtractedJobDetails
from backend.services.ollama_service import ollama_service
from backend.tools.resume_parser import ResumeParser

logger = logging.getLogger("agent_kitkat.job_reader")

EXTRACTION_SYSTEM_PROMPT = """You are a job requirement extraction engine.
Analyze the provided job description and output ONLY a valid JSON object.
Do NOT include explanations, preamble, or markdown formatting outside the JSON.
Schema:
{
  "company_name": "Company Name",
  "job_title": "Job Title",
  "job_description": "Brief 2-3 sentence overview",
  "required_qualifications": ["list of qualification strings"],
  "required_degree": "Degree name or null (e.g. B.Tech, Any Degree)",
  "graduation_eligibility": [2026, 2027],
  "minimum_cgpa": 7.5,
  "required_skills": ["Python", "React"],
  "experience_requirements": "Fresher or 0-1 years",
  "work_location": "Bangalore",
  "work_mode": "Remote",
  "salary_or_stipend": "₹25,000/month",
  "application_deadline": null
}"""


class JobReaderAgent:
    """Agent responsible for ingesting raw job text and extracting structured requirements."""

    @staticmethod
    def extract_deterministic_features(text: str) -> Dict[str, Any]:
        """
        Deterministic regex-based extraction to augment or fallback LLM parsing.
        """
        features: Dict[str, Any] = {}

        # 1. Deterministic Technical Skills using KNOWN_TECH_SKILLS
        features["required_skills"] = ResumeParser.extract_skills(text)

        # 2. Work Mode
        lower = text.lower()
        if "remote" in lower or "work from home" in lower or "wfh" in lower:
            features["work_mode"] = "Remote"
        elif "hybrid" in lower:
            features["work_mode"] = "Hybrid"
        elif "onsite" in lower or "in-office" in lower or "in office" in lower:
            features["work_mode"] = "Onsite"
        else:
            features["work_mode"] = "Unknown"

        # 3. CGPA pattern (e.g. "8.0 CGPA", "min CGPA 7.5", "CGPA: 8.0")
        cgpa_match = re.search(r"\b(?:cgpa|gpa|pointer)\s*(?:of|>=|:|min|minimum)?\s*([6-9](?:\.[0-9]{1,2})?)\b", lower)
        if cgpa_match:
            try:
                features["minimum_cgpa"] = float(cgpa_match.group(1))
            except ValueError:
                features["minimum_cgpa"] = None
        else:
            features["minimum_cgpa"] = None

        # 4. Graduation Year / Batch (e.g. "2026/2027 batch", "graduating in 2027", "batch of 2026")
        grad_matches = re.findall(r"\b(202[4-9]|203[0-5])\b", text)
        if grad_matches:
            # Filter matches appearing near batch/graduation/passout keywords
            relevant_years = set()
            for year in grad_matches:
                pattern = rf"(?:batch|graduat|passout|class of|passing)\s*(?:of|in)?\s*[^.\n]{{0,30}}{year}|{year}\s*[^.\n]{{0,20}}(?:batch|graduat|passout)"
                if re.search(pattern, lower):
                    relevant_years.add(int(year))
            features["graduation_eligibility"] = sorted(list(relevant_years))
        else:
            features["graduation_eligibility"] = []

        # 5. Degree
        if re.search(r"\bb\.?tech\b|\bb\.?e\b|\bbachelor", lower):
            features["required_degree"] = "B.Tech / Bachelor's"
        elif re.search(r"\bm\.?tech\b|\bmca\b|\bmaster", lower):
            features["required_degree"] = "Master's / M.Tech"
        else:
            features["required_degree"] = None

        return features

    @classmethod
    async def analyze_job_text(
        cls,
        text: str,
        provided_title: Optional[str] = None,
        provided_company: Optional[str] = None,
        source_url: Optional[str] = None
    ) -> Tuple[ExtractedJobDetails, float]:
        """
        Runs local Qwen2.5 1.5B with prompt engineering and deterministic augmentation.
        Returns (ExtractedJobDetails, duration_ms).
        """
        start_time = time.perf_counter()

        # Step 1: Run deterministic analysis as guaranteed baseline
        deterministic = cls.extract_deterministic_features(text)

        # Step 2: Prepare clean prompt for Ollama Qwen2.5 1.5B
        # Limit text length to first 4000 characters to prevent high memory or slow inference on 8GB RAM
        truncated_text = text[:4000]

        user_prompt = f"""Extract job requirements from this job description into JSON:

Job Description:
{truncated_text}
"""
        parsed_llm_json: Dict[str, Any] = {}

        try:
            ai_response = await ollama_service.generate_response(
                prompt=user_prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                temperature=0.1  # Low temperature for factual extraction
            )

            raw_ai_text = ai_response.response

            # Extract JSON block
            json_match = re.search(r"\{[\s\S]*\}", raw_ai_text)
            if json_match:
                parsed_llm_json = json.loads(json_match.group(0))
            else:
                logger.warning("No JSON block detected in Ollama response. Falling back to deterministic features.")
        except Exception as e:
            logger.warning("Ollama extraction encountered an issue: %s. Using deterministic features.", str(e))

        # Step 3: Merge LLM extraction with deterministic features
        # Use provided company/title if user passed them explicitly
        final_company = (
            provided_company
            or parsed_llm_json.get("company_name")
            or "Unknown Company"
        )
        final_title = (
            provided_title
            or parsed_llm_json.get("job_title")
            or "Unknown Role"
        )

        # Combine technical skills: union of LLM found and regex confirmed
        llm_skills = parsed_llm_json.get("required_skills", [])
        if isinstance(llm_skills, list):
            combined_skills = set(deterministic["required_skills"])
            for s in llm_skills:
                if isinstance(s, str) and len(s) > 1 and len(s) < 40:
                    combined_skills.add(s.strip())
            final_skills = sorted(list(combined_skills))
        else:
            final_skills = deterministic["required_skills"]

        # Combine graduation batches
        llm_batches = parsed_llm_json.get("graduation_eligibility", [])
        combined_batches = set(deterministic["graduation_eligibility"])
        if isinstance(llm_batches, list):
            for b in llm_batches:
                try:
                    combined_batches.add(int(b))
                except (ValueError, TypeError):
                    pass
        final_batches = sorted(list(combined_batches))

        # Minimum CGPA
        final_cgpa = deterministic.get("minimum_cgpa") or parsed_llm_json.get("minimum_cgpa")
        if isinstance(final_cgpa, (int, float)):
            final_cgpa = float(final_cgpa)
        else:
            final_cgpa = None

        # Work Mode
        raw_mode = str(parsed_llm_json.get("work_mode", "")).lower()
        if "remote" in raw_mode or "wfh" in raw_mode:
            final_work_mode = "Remote"
        elif "hybrid" in raw_mode:
            final_work_mode = "Hybrid"
        elif "onsite" in raw_mode or "office" in raw_mode or "in-office" in raw_mode:
            final_work_mode = "Onsite"
        else:
            final_work_mode = deterministic["work_mode"]

        # Required degree
        final_degree = parsed_llm_json.get("required_degree") or deterministic.get("required_degree")

        # Qualifications list
        quals = parsed_llm_json.get("required_qualifications", [])
        if not isinstance(quals, list):
            quals = []

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        extracted = ExtractedJobDetails(
            company_name=str(final_company).strip(),
            job_title=str(final_title).strip(),
            job_description=str(parsed_llm_json.get("job_description", text[:300])).strip(),
            required_qualifications=[str(q).strip() for q in quals if q],
            required_degree=str(final_degree) if final_degree else None,
            graduation_eligibility=final_batches,
            minimum_cgpa=final_cgpa,
            required_skills=final_skills,
            experience_requirements=parsed_llm_json.get("experience_requirements"),
            work_location=str(parsed_llm_json.get("work_location", "Not Specified")).strip(),
            work_mode=str(final_work_mode).strip(),
            salary_or_stipend=parsed_llm_json.get("salary_or_stipend"),
            application_deadline=parsed_llm_json.get("application_deadline"),
            application_url=source_url,
            job_id=parsed_llm_json.get("job_id")
        )

        return extracted, duration_ms
