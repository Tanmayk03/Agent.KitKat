"""
Agent KitKat - Resume Parser Tool
Extracts text from PDF/DOCX resumes, segments structured sections,
and performs deterministic skill extraction & verification against profile.

Strict Rule: NEVER invent or hallucinate skills or qualifications.
Only extract what is explicitly present in the resume file.
"""

import os
import re
import logging
from typing import Dict, Any, List, Set, Tuple
from pypdf import PdfReader
from docx import Document

logger = logging.getLogger("agent_kitkat.resume_parser")

# Comprehensive dictionary of technical skills and variations
# Mapped to canonical names
KNOWN_TECH_SKILLS: Dict[str, List[str]] = {
    "Python": [r"\bpython\b", r"\bpython3\b"],
    "Java": [r"\bjava\b(?!\s*script)"],
    "JavaScript": [r"\bjavascript\b", r"\bjs\b"],
    "TypeScript": [r"\btypescript\b", r"\bts\b"],
    "C": [r"\bc\b(?![#+])"],
    "C++": [r"\bc\+\+\b", r"\bcpp\b"],
    "C#": [r"\bc#\b", r"\bc-sharp\b"],
    "Go": [r"\bgolang\b", r"\bgo\b(?!\s*(?:to|through|on|ahead))"],
    "Rust": [r"\brust\b"],
    "SQL": [r"\bsql\b", r"\bstructured query language\b"],
    "HTML": [r"\bhtml\b", r"\bhtml5\b"],
    "CSS": [r"\bcss\b", r"\bcss3\b"],
    "React": [r"\breact\b", r"\breact\.?js\b", r"\breactjs\b"],
    "Node.js": [r"\bnode\.?js\b", r"\bnodejs\b", r"\bnode\b"],
    "Next.js": [r"\bnext\.?js\b", r"\bnextjs\b"],
    "Express.js": [r"\bexpress\.?js\b", r"\bexpress\b"],
    "Django": [r"\bdjango\b"],
    "FastAPI": [r"\bfastapi\b"],
    "Flask": [r"\bflask\b"],
    "Spring Boot": [r"\bspring boot\b", r"\bspringboot\b", r"\bspring framework\b"],
    "Tailwind CSS": [r"\btailwind\b", r"\btailwindcss\b"],
    "Bootstrap": [r"\bbootstrap\b"],
    "Redux": [r"\bredux\b"],
    "Vue.js": [r"\bvue\b", r"\bvue\.?js\b"],
    "Angular": [r"\bangular\b", r"\bangularjs\b"],
    "PostgreSQL": [r"\bpostgres\b", r"\bpostgresql\b"],
    "MySQL": [r"\bmysql\b"],
    "MongoDB": [r"\bmongodb\b", r"\bmongo\b"],
    "Redis": [r"\bredis\b"],
    "SQLite": [r"\bsqlite\b", r"\bsqlite3\b"],
    "Docker": [r"\bdocker\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "Git": [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"],
    "Linux": [r"\blinux\b", r"\bubuntu\b", r"\bunix\b"],
    "AWS": [r"\baws\b", r"\bamazon web services\b"],
    "Azure": [r"\bazure\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle cloud\b", r"\bgoogle cloud platform\b"],
    "Machine Learning": [r"\bmachine learning\b", r"\bml\b"],
    "Deep Learning": [r"\bdeep learning\b", r"\bdl\b"],
    "Artificial Intelligence": [r"\bartificial intelligence\b", r"\bai\b"],
    "Data Science": [r"\bdata science\b"],
    "Data Engineering": [r"\bdata engineering\b", r"\bdata pipelines?\b"],
    "TensorFlow": [r"\btensorflow\b", r"\btf\b"],
    "PyTorch": [r"\bpytorch\b"],
    "Scikit-learn": [r"\bscikit-learn\b", r"\bge-learn\b", r"\bsklearn\b"],
    "Pandas": [r"\bpandas\b"],
    "NumPy": [r"\bnumpy\b"],
    "Natural Language Processing": [r"\bnlp\b", r"\bnatural language processing\b"],
    "Computer Vision": [r"\bcomputer vision\b", r"\bcv\b"],
    "REST API": [r"\brest\b", r"\brestful\b", r"\brest api\b", r"\brest apis\b"],
    "GraphQL": [r"\bgraphql\b"],
    "CI/CD": [r"\bci/cd\b", r"\bcontinuous integration\b"],
    "Web development": [r"\bweb development\b", r"\bfull stack\b", r"\bfrontend\b", r"\bbackend\b"],
}


class ResumeParser:
    """Parser for extracting raw text, structured sections, and skills from resume files."""

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Extract all textual content from a PDF file using pypdf."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Resume PDF not found: {file_path}")

        extracted_text_blocks = []
        try:
            reader = PdfReader(file_path)
            for page_idx, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    extracted_text_blocks.append(page_text)
        except Exception as e:
            logger.error("Failed to parse PDF %s: %s", file_path, str(e))
            raise ValueError(f"Could not read PDF resume: {str(e)}")

        full_text = "\n".join(extracted_text_blocks)
        # Normalize excessive newlines and whitespace
        return re.sub(r"\n{3,}", "\n\n", full_text).strip()

    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """Extract all textual content from a DOCX file using python-docx."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Resume DOCX not found: {file_path}")

        extracted_text_blocks = []
        try:
            doc = Document(file_path)
            for p in doc.paragraphs:
                if p.text.strip():
                    extracted_text_blocks.append(p.text.strip())

            # Also read tables if present
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        extracted_text_blocks.append(" | ".join(row_text))
        except Exception as e:
            logger.error("Failed to parse DOCX %s: %s", file_path, str(e))
            raise ValueError(f"Could not read DOCX resume: {str(e)}")

        full_text = "\n".join(extracted_text_blocks)
        return re.sub(r"\n{3,}", "\n\n", full_text).strip()

    @classmethod
    def parse_file(cls, file_path: str) -> str:
        """Parse resume file based on extension (.pdf or .docx)."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return cls.extract_text_from_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            return cls.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Only PDF and DOCX are supported.")

    @classmethod
    def extract_skills(cls, text: str) -> List[str]:
        """
        Scan text for known technical skills using bounded regex patterns.
        Deterministic and deterministic only. Never hallucinates.
        """
        found_skills: Set[str] = set()
        lower_text = text.lower()

        for canonical_name, patterns in KNOWN_TECH_SKILLS.items():
            for pattern in patterns:
                if re.search(pattern, lower_text, re.IGNORECASE):
                    found_skills.add(canonical_name)
                    break

        return sorted(list(found_skills))

    @classmethod
    def segment_sections(cls, text: str) -> Dict[str, List[str]]:
        """
        Heuristic section segmenter that groups lines into standard resume categories:
        education, experience, projects, certifications, skills.
        """
        sections: Dict[str, List[str]] = {
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "skills": []
        }

        # Heading patterns
        heading_map = {
            "education": [r"^education", r"^academic background", r"^qualifications"],
            "experience": [r"^experience", r"^work experience", r"^employment", r"^internships"],
            "projects": [r"^projects", r"^personal projects", r"^academic projects"],
            "certifications": [r"^certifications", r"^licenses", r"^credentials", r"^achievements"],
            "skills": [r"^skills", r"^technical skills", r"^technologies", r"^core competencies"]
        }

        current_section = None
        lines = text.split("\n")

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue

            # Check if this line is a heading
            matched_section = None
            lower_line = trimmed.lower()
            if len(trimmed) < 40:  # Headings are typically short
                for sec_name, patterns in heading_map.items():
                    if any(re.match(p, lower_line) for p in patterns):
                        matched_section = sec_name
                        break

            if matched_section:
                current_section = matched_section
                continue

            if current_section:
                sections[current_section].append(trimmed)

        return sections

    @classmethod
    def verify_profile_skills(
        cls,
        resume_text: str,
        current_verified: List[str],
        current_unverified: List[str]
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Cross-verify profile skills against resume text.
        Returns:
            (new_verified_skills, remaining_unverified_skills, all_extracted_skills)
        """
        extracted_skills = cls.extract_skills(resume_text)
        extracted_set_lower = {s.lower() for s in extracted_skills}

        # Combine any already verified with newly verified
        verified_set = set(current_verified)
        unverified_remaining = []

        for skill in current_unverified:
            # Check canonical match or regex pattern match in resume text
            skill_lower = skill.lower()
            matched = False

            if skill_lower in extracted_set_lower:
                matched = True
            else:
                # Check regex in resume text
                patterns = KNOWN_TECH_SKILLS.get(skill, [rf"\b{re.escape(skill_lower)}\b"])
                if any(re.search(p, resume_text, re.IGNORECASE) for p in patterns):
                    matched = True

            if matched:
                verified_set.add(skill)
            else:
                unverified_remaining.append(skill)

        # Also add any newly detected technical skills from the resume into verified
        for skill in extracted_skills:
            verified_set.add(skill)

        final_verified = sorted(list(verified_set))
        final_unverified = sorted(list(set(unverified_remaining) - set(final_verified)))

        return final_verified, final_unverified, extracted_skills
