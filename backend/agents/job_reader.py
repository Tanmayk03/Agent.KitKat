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
Copy values from the text. If the text does not state a value, use null (or [] for lists).
Never guess, never use example values.
Keys and types:
{
  "company_name": string or null,
  "job_title": string or null,
  "job_description": string (2-3 sentence summary of the text) or null,
  "required_qualifications": [string],
  "required_degree": string or null,
  "graduation_eligibility": [integer year],
  "minimum_cgpa": number or null,
  "required_skills": [string],
  "experience_requirements": string or null,
  "work_location": string or null,
  "work_mode": "Remote" | "Hybrid" | "Onsite" | null,
  "salary_or_stipend": string or null,
  "application_deadline": string or null
}"""

SENIOR_TITLE_PATTERNS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\bstaff\b", r"\blead\b", r"\bprincipal\b", r"\barchitect\b",
    r"\bdirector\b", r"\bhead\b", r"\bmanager\b", r"\btier\s*(?:ii|iii|iv|2|3|4)\b",
]
EARLY_CAREER_PATTERNS = [
    r"\bintern\b", r"\binternship\b", r"\bfresher\b", r"\bgraduate\b", r"\bco-?op\b", r"\bjunior\b",
    r"\btrainee\b", r"\bentry\s*-?level\b", r"\bworking\s*student\b", r"\bnew\s*grad\b",
]


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def is_grounded(value: Any, source_text: str) -> bool:
    """
    True if every significant token of an LLM-produced value occurs in the source text.
    Used to drop values the model invented or copied from an example.
    """
    if value is None:
        return False
    toks = [t for t in _tokens(str(value)) if len(t) >= 2 or t.isdigit()]
    if not toks:
        return False
    source_tokens = set(_tokens(source_text))
    return all(t in source_tokens for t in toks)


class JobReaderAgent:
    """Agent responsible for ingesting raw job text and extracting structured requirements."""

    @staticmethod
    def extract_deterministic_features(text: str, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Deterministic regex-based extraction (no LLM). Missing information stays None / [].
        `title`, when known, is used for seniority detection; otherwise the first line of text is used.
        """
        features: Dict[str, Any] = {}
        text = text or ""
        lower = text.lower()

        # 1. Technical skills
        features["required_skills"] = ResumeParser.extract_skills(text)

        # 2. Work mode (ignore negated mentions such as "not remote" / "no remote")
        positive_remote = re.search(r"(?<!not )(?<!no )\b(?:fully |100% )?remote\b|\bwork from home\b|\bwfh\b", lower)
        negated_remote = re.search(r"\b(?:not|no|non)[\s-]+remote\b", lower)
        if "hybrid" in lower:
            features["work_mode"] = "Hybrid"
        elif positive_remote and not negated_remote:
            features["work_mode"] = "Remote"
        elif re.search(r"\bon-?site\b|\bin-office\b|\bin office\b|\bwork from office\b|\bwfo\b", lower):
            features["work_mode"] = "Onsite"
        else:
            features["work_mode"] = "Unknown"

        # 3. CGPA cutoff (e.g. "minimum CGPA of 7.5", "CGPA: 8.0", "7.0 CGPA")
        cgpa_match = (
            re.search(r"\b(?:c\.?g\.?p\.?a|gpa|pointer)\s*(?:of|>=|:|min(?:imum)?|above|at least|\s)*\s*([5-9](?:\.[0-9]{1,2})?|10(?:\.0+)?)\b", lower)
            or re.search(r"\b([5-9](?:\.[0-9]{1,2})?)\s*(?:\+\s*)?(?:c\.?g\.?p\.?a|gpa)\b", lower)
        )
        features["minimum_cgpa"] = float(cgpa_match.group(1)) if cgpa_match else None

        # 4. Graduation year / batch (years near batch/graduation keywords only)
        relevant_years = set()
        for year in set(re.findall(r"\b(202[4-9]|203[0-5])\b", text)):
            pattern = (
                rf"(?:batch|graduat|passout|pass-out|passing out|class of|passing|year of passing)\s*(?:of|in)?\s*[^.\n]{{0,30}}{year}"
                rf"|{year}\s*[^.\n]{{0,20}}(?:batch|graduat|passout|pass-out|passing)"
            )
            if re.search(pattern, lower):
                relevant_years.add(int(year))
        features["graduation_eligibility"] = sorted(relevant_years)

        # 5. Degree ("B.E." needs the dots: the plain word "be" is not a degree)
        if re.search(r"\bb\.\s?tech\b|\bbtech\b|\bb\.\s?e\.|\bbachelor'?s?\b|\bundergraduate degree\b", lower):
            features["required_degree"] = "B.Tech / B.E. / Bachelor's"
        elif re.search(r"\bm\.\s?tech\b|\bmtech\b|\bmca\b|\bmaster'?s?\b", lower):
            features["required_degree"] = "Master's / M.Tech / MCA"
        else:
            features["required_degree"] = None

        # 6. Location from an explicit "Location:" line
        loc_match = re.search(r"^\s*(?:job\s+)?location\s*[:\-–]\s*(.{2,120})$", text, re.IGNORECASE | re.MULTILINE)
        features["location"] = loc_match.group(1).strip() if loc_match else None

        # 7. Experience level: seniority from the TITLE only (body text mentions "senior engineers" often)
        title_text = (title or text.split("\n", 1)[0]).lower()
        exp_match = re.search(r"(\d+)\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)\s*(?:of\s*)?(?:professional\s*|work\s*|relevant\s*)?exp", lower[:3000])
        if any(re.search(pat, title_text) for pat in SENIOR_TITLE_PATTERNS):
            features["experience_required"] = "Senior / Experienced (from title)"
        elif any(re.search(pat, title_text) for pat in EARLY_CAREER_PATTERNS):
            features["experience_required"] = "Intern / Fresher (from title)"
        elif exp_match:
            features["experience_required"] = exp_match.group(0)
        elif any(re.search(pat, lower[:1500]) for pat in EARLY_CAREER_PATTERNS):
            features["experience_required"] = "Intern / Fresher (from description)"
        else:
            features["experience_required"] = None

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
        deterministic = cls.extract_deterministic_features(text, title=provided_title)

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
        # Every LLM string value must be traceable to the source text; otherwise it is dropped.
        def grounded(key: str) -> Optional[str]:
            val = parsed_llm_json.get(key)
            if isinstance(val, str) and val.strip() and is_grounded(val, text):
                return val.strip()
            return None

        final_company = provided_company or grounded("company_name") or "Unknown Company"
        final_title = provided_title or grounded("job_title") or "Unknown Role"

        # Combine technical skills: union of LLM found and regex confirmed
        llm_skills = parsed_llm_json.get("required_skills", [])
        if isinstance(llm_skills, list):
            combined_skills = set(deterministic["required_skills"])
            for s in llm_skills:
                if isinstance(s, str) and 1 < len(s) < 40 and is_grounded(s, text):
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
                    year = int(b)
                except (ValueError, TypeError):
                    continue
                if str(year) in text:  # only years actually present in the posting
                    combined_batches.add(year)
        final_batches = sorted(list(combined_batches))

        # Minimum CGPA
        final_cgpa = deterministic.get("minimum_cgpa")
        llm_cgpa = parsed_llm_json.get("minimum_cgpa")
        if final_cgpa is None and isinstance(llm_cgpa, (int, float)) and 0 < float(llm_cgpa) <= 10:
            # accept only if the number literally appears in the text near a CGPA/GPA mention
            num = f"{float(llm_cgpa):g}"
            if re.search(rf"(?:c\.?g\.?p\.?a|gpa|pointer)[^\n]{{0,40}}\b{re.escape(num)}\b|\b{re.escape(num)}\b[^\n]{{0,20}}(?:c\.?g\.?p\.?a|gpa)", text.lower()):
                final_cgpa = float(llm_cgpa)

        # Work Mode (deterministic first; LLM only fills an Unknown)
        raw_mode = str(parsed_llm_json.get("work_mode") or "").lower() if deterministic["work_mode"] == "Unknown" else deterministic["work_mode"].lower()
        if "remote" in raw_mode or "wfh" in raw_mode:
            final_work_mode = "Remote"
        elif "hybrid" in raw_mode:
            final_work_mode = "Hybrid"
        elif "onsite" in raw_mode or "office" in raw_mode or "in-office" in raw_mode:
            final_work_mode = "Onsite"
        else:
            final_work_mode = deterministic["work_mode"]

        # Required degree
        final_degree = deterministic.get("required_degree") or grounded("required_degree")

        # Qualifications list
        quals = parsed_llm_json.get("required_qualifications", [])
        if not isinstance(quals, list):
            quals = []
        quals = [q for q in quals if isinstance(q, str) and is_grounded(q, text)]

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        extracted = ExtractedJobDetails(
            company_name=str(final_company).strip(),
            job_title=str(final_title).strip(),
            job_description=str(parsed_llm_json.get("job_description") or text[:300]).strip(),
            required_qualifications=[str(q).strip() for q in quals if q],
            required_degree=str(final_degree) if final_degree else None,
            graduation_eligibility=final_batches,
            minimum_cgpa=final_cgpa,
            required_skills=final_skills,
            experience_requirements=deterministic.get("experience_required") or grounded("experience_requirements"),
            work_location=deterministic.get("location") or grounded("work_location") or "Not stated",
            work_mode=str(final_work_mode).strip(),
            salary_or_stipend=grounded("salary_or_stipend"),
            application_deadline=grounded("application_deadline"),
            application_url=source_url,
            job_id=None
        )

        return extracted, duration_ms
