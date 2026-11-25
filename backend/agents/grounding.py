"""
Agent KitKat - Grounding checker for generated application text.

Flags sentences in a cover letter / screening answer that make claims your profile and
active resume do not support. It is deliberately strict and deterministic: a flag means
"a human must check this", not "this is false".

Checks
- skill        a technical skill that is not among your verified / resume skills
- number       a metric or count ("40% faster", "3 years", "500+ users") not present in your
               profile, resume or the job posting
- cgpa         a CGPA/GPA value different from your profile
- employer     "interned / worked at X" where X is not in your profile or resume
- certification certification claims when your profile and resume list none
- placeholder  unfilled placeholders ("[Add ...]", NEEDS_YOUR_INPUT)
"""

import re
from typing import Any, Dict, Iterable, List, Optional

from backend.tools.resume_parser import ResumeParser

NUMBER_CLAIM = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(%|\+|x\b|k\b|lakh|lpa|users|customers|clients|downloads|requests|"
    r"years?|months?|projects|hackathons|members|people|teams|apps|stars|contributors|repositories|ms\b|seconds)",
    re.IGNORECASE,
)
EMPLOYER_CLAIM = re.compile(
    r"\b(?:interned|internship|worked|working|employed|experience|role)\s+(?:as\s+[\w\s]{2,40}?\s+)?(?:at|with)\s+"
    r"([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,3})"
)
CGPA_CLAIM = re.compile(r"\b(?:c\.?g\.?p\.?a|gpa)\b[^\d\n]{0,15}(\d{1,2}(?:\.\d{1,2})?)", re.IGNORECASE)
CERT_CLAIM = re.compile(r"\b(certified|certification|certificate)\b", re.IGNORECASE)
PLACEHOLDER = re.compile(r"\[[^\]]{3,}\]|NEEDS_YOUR_INPUT")
FIRST_PERSON = re.compile(r"\b(i|i'm|i've|i'd|my|me|myself)\b", re.IGNORECASE)


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def build_fact_corpus(profile, resume_text: str = "", job_text: str = "") -> str:
    """Everything a claim may legitimately be traced back to."""
    bits: List[str] = [
        profile.full_name or "", profile.location or "", profile.expected_stipend or "",
        " ".join(str(v) for v in (profile.education or {}).values() if v is not None),
        " ".join(profile.verified_skills or []),
    ]
    for coll in (profile.projects or [], profile.work_experience or [], profile.certifications or []):
        for item in coll:
            bits.append(" ".join(str(v) for v in item.values()) if isinstance(item, dict) else str(item))
    bits.append(resume_text or "")
    bits.append(job_text or "")
    return "\n".join(bits)


def check_text(text: str, where: str, *, candidate_skills: Iterable[str], corpus: str,
               profile_cgpa: Optional[float], has_certifications: bool, company: str = "",
               job_title: str = "") -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    have = {s.lower() for s in candidate_skills}
    corpus_low = corpus.lower()
    company_low = (company or "").lower()

    def flag(kind: str, sentence: str, message: str):
        issues.append({"where": where, "kind": kind, "sentence": sentence[:300], "issue": message})

    for sent in _sentences(text):
        if PLACEHOLDER.search(sent):
            flag("placeholder", sent, "Placeholder not filled in.")
        # Skills: only first-person claims count, and naming the role/company ("the AI/ML Intern role") is not a claim
        claim = sent
        for name in (job_title, company):
            if name:
                claim = re.sub(re.escape(name), " ", claim, flags=re.IGNORECASE)
        for skill in (ResumeParser.extract_skills(claim) if FIRST_PERSON.search(claim) else []):
            if skill.lower() not in have:
                flag("skill", sent, f"Mentions {skill}, which is not a verified skill in your profile/resume.")
        for m in NUMBER_CLAIM.finditer(sent):
            num = m.group(1).replace(",", "")
            if not re.search(rf"(?<![\d.]){re.escape(num)}(?![\d])", corpus_low):
                flag("number", sent, f"'{m.group(0).strip()}' does not appear in your profile, resume or the job posting.")
        m = CGPA_CLAIM.search(sent)
        if m and profile_cgpa is not None and abs(float(m.group(1)) - float(profile_cgpa)) > 0.005:
            flag("cgpa", sent, f"States CGPA {m.group(1)}; your profile says {profile_cgpa}.")
        for m in EMPLOYER_CLAIM.finditer(sent):
            employer = m.group(1).strip().rstrip(".,;:")
            if employer.lower() == company_low or employer.lower() in company_low:
                continue  # talking about the company being applied to
            if employer.lower() not in corpus_low:
                flag("employer", sent, f"Claims experience with '{employer}', which is not in your profile or resume.")
        if CERT_CLAIM.search(sent) and not has_certifications:
            flag("certification", sent, "Mentions a certification, but your profile and resume list none.")
    # de-duplicate identical findings
    seen, unique = set(), []
    for i in issues:
        key = (i["where"], i["kind"], i["issue"])
        if key not in seen:
            seen.add(key)
            unique.append(i)
    return unique


def check_draft(cover_letter: str, custom_answers: Dict[str, Any], *, profile, candidate_skills: Iterable[str],
                resume_text: str = "", job=None) -> List[Dict[str, Any]]:
    """Grounding report for a whole draft."""
    job_text = "\n".join(x for x in ((job.title if job else ""), (job.company if job else ""), (job.raw_text if job else "")) if x)
    corpus = build_fact_corpus(profile, resume_text, job_text)
    edu = profile.education or {}
    try:
        cgpa = float(edu["cgpa"]) if edu.get("cgpa") not in (None, "") else None
    except (TypeError, ValueError):
        cgpa = None
    has_certs = bool(profile.certifications) or bool(re.search(r"certif", resume_text or "", re.I))
    # Skills you may mention: verified/resume skills + anything named in your own profile/resume
    # (e.g. "Data Science" in your specialization). Skills that only appear in the JOB posting are not yours.
    skills = list(candidate_skills) + ResumeParser.extract_skills(build_fact_corpus(profile, resume_text, ""))
    common = dict(candidate_skills=skills, corpus=corpus, profile_cgpa=cgpa, has_certifications=has_certs,
                  company=job.company if job else "", job_title=job.title if job else "")
    report = check_text(cover_letter or "", "cover_letter", **common)
    for key, val in (custom_answers or {}).items():
        report += check_text(str(val or ""), f"answers.{key}", **common)
    return report
