"""
Agent KitKat - Job requirement extraction with provenance and evidence.

Every requirement is returned as a Requirement:
    value       what the posting requires (None when not stated)
    provenance  "explicit"  - stated in the posting text (evidence = the quoted sentence)
                "inferred"  - derived from structured source fields or the job title
                "missing"   - the posting does not say
    evidence    the exact sentence / field the value came from (shown in the UI)

Deterministic only (regular expressions over the posting text and stored job fields).
Nothing here calls the language model, so nothing can be invented.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

COUNTRY_WORDS = {
    "united states": "United States", "u.s.": "United States", "usa": "United States", "us": "United States",
    "united kingdom": "United Kingdom", "uk": "United Kingdom", "canada": "Canada", "india": "India",
    "germany": "Germany", "european union": "European Union", "eu": "European Union", "australia": "Australia",
    "singapore": "Singapore", "netherlands": "Netherlands", "ireland": "Ireland", "france": "France",
}
_COUNTRY_RE = "|".join(sorted((re.escape(k) for k in COUNTRY_WORDS), key=len, reverse=True))


@dataclass
class Requirement:
    value: Any = None
    provenance: str = "missing"
    evidence: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"value": self.value, "provenance": self.provenance, "evidence": self.evidence}


@dataclass
class JobRequirements:
    graduation_years: Requirement = field(default_factory=Requirement)
    min_cgpa: Requirement = field(default_factory=Requirement)
    degree: Requirement = field(default_factory=Requirement)
    max_backlogs: Requirement = field(default_factory=Requirement)
    experience_years: Requirement = field(default_factory=Requirement)
    level: Requirement = field(default_factory=Requirement)          # "intern/fresher" | "senior" | None
    work_authorization: Requirement = field(default_factory=Requirement)  # country the posting requires
    no_sponsorship: Requirement = field(default_factory=Requirement)
    internship_duration: Requirement = field(default_factory=Requirement)
    relocation: Requirement = field(default_factory=Requirement)
    full_time_required: Requirement = field(default_factory=Requirement)

    def as_dict(self) -> Dict[str, Dict[str, Any]]:
        return {k: v.as_dict() for k, v in self.__dict__.items()}


def sentence_around(text: str, start: int, end: int, max_len: int = 200) -> str:
    """The sentence (or line) containing text[start:end], trimmed for display."""
    left = max(text.rfind("\n", 0, start), text.rfind(". ", 0, start))
    left = 0 if left < 0 else left + 1
    candidates = [i for i in (text.find("\n", end), text.find(". ", end)) if i != -1]
    right = min(candidates) + 1 if candidates else len(text)
    snippet = " ".join(text[left:right].split())
    if len(snippet) > max_len:
        mid = max(0, (start - left) - max_len // 3)
        snippet = ("…" if mid else "") + snippet[mid:mid + max_len].strip() + "…"
    return snippet


def _search(pattern: str, text: str, flags=re.IGNORECASE):
    return re.search(pattern, text, flags)


SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|staff|lead|principal|architect|director|head|manager)\b", re.I)
EARLY_TITLE = re.compile(r"\b(intern|internship|fresher|graduate|new\s*grad|co-?op|junior|jr\.?|trainee|entry[\s-]*level|working\s*student|apprentice)\b", re.I)


def extract_requirements(text: str, title: str = "", job_fields: Optional[Dict[str, Any]] = None) -> JobRequirements:
    """
    Extract hard requirements from a posting.
    `job_fields` may carry values already stored on the Job (e.g. graduation_eligibility / minimum_cgpa
    from Mode B analysis); they are used as "inferred" only when the text itself has no explicit match.
    """
    text = text or ""
    jf = job_fields or {}
    req = JobRequirements()

    # --- Graduation batch -----------------------------------------------------
    years, ev = set(), None
    for m in re.finditer(r"\b(20[2-3]\d)\b", text):
        sentence = sentence_around(text, m.start(), m.end(), max_len=10_000)
        low = sentence.lower()
        if not re.search(r"batch|graduat|passout|pass-out|passing|class of|year of passing|students", low):
            continue
        # "2026/2027 students are not eligible" lists EXCLUDED batches
        after = low[low.find(m.group(1)):]
        if re.search(r"not eligible|ineligible|not allowed|excluded|cannot apply|can't apply|need not apply", after[:80]):
            continue
        if not re.search(r"batch|graduat|passout|pass-out|passing|class of|year of passing", low) and "eligible" not in low:
            continue
        years.add(int(m.group(1)))
        ev = ev or sentence_around(text, m.start(), m.end())
    if years:
        req.graduation_years = Requirement(sorted(years), "explicit", ev)
    elif jf.get("graduation_eligibility"):
        req.graduation_years = Requirement(sorted(int(y) for y in jf["graduation_eligibility"]), "inferred",
                                           "Stored from earlier analysis of this posting")

    # --- Minimum CGPA ---------------------------------------------------------
    m = (_search(r"\b(?:c\.?g\.?p\.?a|gpa|pointer)\b[^\n.\d]{0,30}?([5-9](?:\.\d{1,2})?|10(?:\.0+)?)\b", text)
         or _search(r"\b([5-9](?:\.\d{1,2})?)\s*\+?\s*(?:/\s*10\s*)?(?:c\.?g\.?p\.?a|gpa)\b", text))
    if m:
        req.min_cgpa = Requirement(float(m.group(1)), "explicit", sentence_around(text, m.start(), m.end()))
    elif jf.get("minimum_cgpa") is not None:
        req.min_cgpa = Requirement(float(jf["minimum_cgpa"]), "inferred", "Stored from earlier analysis of this posting")
    else:
        m = _search(r"\b(\d{2})\s*%\s*(?:or above|and above|aggregate|throughout|in (?:10th|12th|graduation))", text)
        if m:
            req.min_cgpa = Requirement(None, "explicit", sentence_around(text, m.start(), m.end()))  # % cut-off: needs a human

    # --- Degree ---------------------------------------------------------------
    m = _search(r"\b(b\.\s?tech|btech|b\.\s?e\.|bachelor'?s?(?:\s+degree)?(?:\s+in\s+[a-z ,/&]+)?|m\.\s?tech|mtech|mca|master'?s?(?:\s+degree)?|ph\.?\s?d|any (?:degree|graduate)|undergraduate degree)", text)
    if m:
        req.degree = Requirement(" ".join(m.group(1).split()), "explicit", sentence_around(text, m.start(), m.end()))
    elif jf.get("required_degree"):
        req.degree = Requirement(jf["required_degree"], "inferred", "Stored from earlier analysis of this posting")

    # --- Backlogs -------------------------------------------------------------
    m = _search(r"\b(no|zero|nil|without any)\s+(?:active\s+|current\s+|standing\s+)?(?:backlogs?|arrears?|kts?)\b", text) \
        or _search(r"\bbacklogs?\s+(?:are\s+)?not\s+allowed\b", text)
    if m:
        req.max_backlogs = Requirement(0, "explicit", sentence_around(text, m.start(), m.end()))
    else:
        m = _search(r"\b(?:max(?:imum)?|up to|not more than)\s+(\d)\s+(?:active\s+)?backlogs?\b", text)
        if m:
            req.max_backlogs = Requirement(int(m.group(1)), "explicit", sentence_around(text, m.start(), m.end()))

    # --- Level / experience ---------------------------------------------------
    if title and SENIOR_TITLE.search(title):
        req.level = Requirement("senior", "inferred", f"Job title: {title}")
    elif title and EARLY_TITLE.search(title):
        req.level = Requirement("intern/fresher", "inferred", f"Job title: {title}")
    else:
        m = _search(r"\b(internship|intern role|summer intern|fresher|freshers|entry[\s-]level|new grad(?:uate)?s?)\b", text[:2000])
        if m:
            req.level = Requirement("intern/fresher", "explicit", sentence_around(text, m.start(), m.end()))
    m = _search(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)\s*(?:of\s*)?(?:professional\s+|industry\s+|work\s+|relevant\s+|hands-on\s+)?(?:experience|exp)\b", text[:4000])
    if m:
        req.experience_years = Requirement(int(m.group(1)), "explicit", sentence_around(text, m.start(), m.end()))

    # --- Work authorisation / sponsorship ------------------------------------
    m = _search(rf"\b(?:authori[sz]ed|eligible|legally (?:able|permitted)|right) to work in (?:the )?({_COUNTRY_RE})\b", text)
    if m:
        country = COUNTRY_WORDS.get(m.group(1).lower(), m.group(1))
        req.work_authorization = Requirement(country, "explicit", sentence_around(text, m.start(), m.end()))
    m = _search(r"\b(?:(?:will not|won't|cannot|can't|unable to|do not|don't|does not)\s+(?:provide\s+|offer\s+)?sponsor|no (?:visa )?sponsorship|sponsorship (?:is )?not (?:available|provided))", text)
    if m:
        req.no_sponsorship = Requirement(True, "explicit", sentence_around(text, m.start(), m.end()))

    # --- Other hard requirements ----------------------------------------------
    m = _search(r"\b(\d{1,2})\s*(?:-|to)?\s*(?:\d{1,2}\s*)?(months?|weeks?)\b[^.\n]{0,25}\b(?:internship|duration|long|program)", text) \
        or _search(r"\b(?:duration|internship period|internship length)\s*[:\-]?\s*(\d{1,2})\s*(months?|weeks?)", text)
    if m:
        req.internship_duration = Requirement(f"{m.group(1)} {m.group(2)}", "explicit", sentence_around(text, m.start(), m.end()))
    m = _search(r"\b(?:must|should|required to|willing(?:ness)? to)\s+(?:be\s+(?:willing|able)\s+to\s+)?relocate\b", text)
    if m:
        req.relocation = Requirement(True, "explicit", sentence_around(text, m.start(), m.end()))
    m = _search(r"\b(?:must|should)\s+be\s+available\s+(?:to work\s+)?full[\s-]time\b|\bfull[\s-]time\s+(?:in[\s-]office\s+)?internship\b|\b(?:5|five)\s+days\s+(?:a week\s+)?(?:in|from)\s+(?:the\s+)?office\b", text)
    if m:
        req.full_time_required = Requirement(True, "explicit", sentence_around(text, m.start(), m.end()))

    return req
