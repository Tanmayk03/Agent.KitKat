"""
Agent KitKat - Resume -> profile facts (deterministic, with evidence).

Reads the text of YOUR uploaded resume and proposes profile values. Nothing is applied
automatically: the Resumes page shows each suggestion next to your current value with the
resume line it came from, and you choose which ones to apply.

Also used to cross-check the profile (e.g. "profile CGPA 8.53, resume says 8.44").
"""

import re
from typing import Any, Dict, List, Optional

from backend.tools.resume_parser import ResumeParser

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?91[\s-]?)?(?<!\d)[6-9]\d{4}[\s-]?\d{5}(?!\d)|\+\d{1,3}[\s-]?\d{3,4}[\s-]?\d{3,4}[\s-]?\d{3,4}")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[\w\-%]+/?", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+/?(?![\w/])", re.I)
CGPA_RE = re.compile(r"\b(?:c\.?g\.?p\.?a|gpa)\b\s*[:\-–]?\s*(\d{1,2}(?:\.\d{1,2})?)\s*(?:/\s*10(?:\.0+)?)?", re.I)
CGPA_SLASH_RE = re.compile(r"\b(\d(?:\.\d{1,2})?)\s*/\s*10(?:\.0+)?\b")
DEGREE_PATTERNS = [
    (r"\bb\.?\s?tech\b|\bbachelor of technology\b", "B.Tech"),
    (r"\bb\.\s?e\.|\bbachelor of engineering\b", "B.E."),
    (r"\bb\.?\s?sc\b|\bbachelor of science\b", "B.Sc"),
    (r"\bbca\b|\bbachelor of computer applications\b", "BCA"),
    (r"\bm\.?\s?tech\b|\bmaster of technology\b", "M.Tech"),
    (r"\bmca\b|\bmaster of computer applications\b", "MCA"),
]
SPEC_RE = re.compile(r"(computer science(?:\s*(?:and|&|\(|with|-|–|,)\s*(?:engineering|data science|artificial intelligence|ai|machine learning|ml)\)?)*"
                     r"|information technology|data science|artificial intelligence(?: and machine learning)?|electronics and communication(?: engineering)?)", re.I)
INSTITUTION_RE = re.compile(r"[^\n|,]*\b(university|institute|college|iit|nit|iiit|bits)\b[^\n|]*", re.I)


def _norm_url(url: str) -> str:
    url = url.rstrip("/")
    return url if url.lower().startswith("http") else f"https://{url}"


def _suggest(field: str, label: str, value: Any, evidence: Optional[str]) -> Dict[str, Any]:
    return {"field": field, "label": label, "suggested": value, "evidence": evidence}


def _line_of(text: str, start: int) -> str:
    left = text.rfind("\n", 0, start) + 1
    right = text.find("\n", start)
    return " ".join(text[left: right if right != -1 else len(text)].split())[:200]


def extract_cgpa(text: str) -> Optional[Dict[str, Any]]:
    m = CGPA_RE.search(text)
    if m:
        val = float(m.group(1))
        if 0 < val <= 10:
            return {"value": val, "evidence": _line_of(text, m.start())}
    m = CGPA_SLASH_RE.search(text)
    if m:
        val = float(m.group(1))
        if 0 < val <= 10:
            return {"value": val, "evidence": _line_of(text, m.start())}
    return None


def extract_profile_facts(raw_text: str, sections: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
    """Return a list of suggestions: {field, label, suggested, evidence}."""
    text = raw_text or ""
    sections = sections or ResumeParser.segment_sections(text)
    edu_text = "\n".join(sections.get("education") or []) or text
    out: List[Dict[str, Any]] = []

    # Name: first line that looks like a person's name
    for line in text.splitlines()[:5]:
        clean = line.strip()
        if 2 <= len(clean.split()) <= 4 and re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", clean) and not re.search(
                r"resume|curriculum|vitae|profile", clean, re.I):
            out.append(_suggest("full_name", "Full name", clean.title() if clean.isupper() else clean, clean))
            break

    m = EMAIL_RE.search(text)
    if m:
        out.append(_suggest("email", "Email", m.group(0), _line_of(text, m.start())))
    m = PHONE_RE.search(text)
    if m:
        digits = re.sub(r"[^\d+]", "", m.group(0))
        if not digits.startswith("+") and len(digits) == 10:
            digits = "+91" + digits
        elif digits.startswith("91") and len(digits) == 12:
            digits = "+" + digits
        out.append(_suggest("phone", "Phone", digits, _line_of(text, m.start())))
    m = LINKEDIN_RE.search(text)
    if m:
        out.append(_suggest("linkedin_url", "LinkedIn", _norm_url(m.group(0)), _line_of(text, m.start())))
    m = GITHUB_RE.search(text)
    if m:
        out.append(_suggest("github_url", "GitHub", _norm_url(m.group(0)), _line_of(text, m.start())))

    # Education
    for pattern, label in DEGREE_PATTERNS:
        m = re.search(pattern, edu_text, re.I)
        if m:
            out.append(_suggest("education.degree", "Degree", label, _line_of(edu_text, m.start())))
            break
    m = SPEC_RE.search(edu_text)
    if m:
        spec = " ".join(m.group(1).split())
        out.append(_suggest("education.specialization", "Specialization", spec[0].upper() + spec[1:], _line_of(edu_text, m.start())))
    m = INSTITUTION_RE.search(edu_text)
    if m:
        out.append(_suggest("education.college", "College / University", " ".join(m.group(0).split()).strip(" -–:"), _line_of(edu_text, m.start())))
    cg = extract_cgpa(edu_text) or extract_cgpa(text)
    if cg:
        out.append(_suggest("education.cgpa", "CGPA", cg["value"], cg["evidence"]))
    years = [(int(y.group(0)), y.start()) for y in re.finditer(r"\b20[1-4]\d\b", edu_text)]
    if years:
        expected = re.search(r"(?:expected|graduating|graduation|class of)[^\n]{0,30}?(20[1-4]\d)", edu_text, re.I)
        if expected:
            out.append(_suggest("education.graduation_year", "Graduation year", int(expected.group(1)), _line_of(edu_text, expected.start())))
        else:
            year, pos = max(years)
            out.append(_suggest("education.graduation_year", "Graduation year", year, _line_of(edu_text, pos)))

    # Skills found literally in the resume
    skills = ResumeParser.extract_skills(text)
    if skills:
        out.append(_suggest("verified_skills", "Skills found in resume", skills, f"{len(skills)} skills matched in the resume text"))

    # Projects: short title-like lines in the Projects section, with the bullets below them
    projects = []
    current = None
    for line in sections.get("projects") or []:
        stripped = line.strip()
        is_bullet = bool(re.match(r"^[•\-*–▪●◦]\s*", stripped))
        if not is_bullet and len(stripped) <= 90 and not stripped.endswith("."):
            name = re.split(r"\s+[|–-]\s+", stripped)[0].strip()
            current = {"name": name, "description": "", "tech_stack": ResumeParser.extract_skills(stripped)}
            projects.append(current)
        elif current is not None:
            body = re.sub(r"^[•\-*–▪●◦]\s*", "", stripped)
            current["description"] = (current["description"] + " " + body).strip()[:500]
            current["tech_stack"] = sorted(set(current["tech_stack"]) | set(ResumeParser.extract_skills(body)))
    projects = [p for p in projects if p["name"]][:8]
    if projects:
        out.append(_suggest("projects", "Projects", projects, f"{len(projects)} project(s) from the Projects section"))
    return out
