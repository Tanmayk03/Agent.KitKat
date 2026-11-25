"""
Agent KitKat - Public Job Discovery Sources (Multi-Source, 100% Real Live Feeds, ₹0 Budget)
Strict Geographic & Career Hierarchy:
1. PRIORITY 1: India Domestic Tech Roles (Delhi NCR, Noida, Gurgaon, Bangalore, Hyderabad, Pune, Remote India, etc.)
2. PRIORITY 2: International Roles ONLY IF REMOTE (Worldwide Remote, Remote in USA, etc.)
3. REJECTED: Any foreign onsite/hybrid role (Zurich, Munich, Amsterdam, Chicago onsite, etc.)
4. CAREER LEVEL: Strictly Intern, Working Student, Fresher, and Entry-Level (Zero Senior / Lead / Staff).

ZERO MOCK DATA. ZERO FABRICATED LISTINGS.

Rules enforced here:
- Fields a source does not provide are left as None (never "Competitive", "Tech Company", "Hybrid", ...).
- Listings without a company or URL are skipped.
- External IDs come from the source only; no positional fallbacks (dedupe is scoped per source).
- Network/HTTP failures raise SourceFetchError so the discovery service can report source health.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import httpx
from bs4 import BeautifulSoup

from backend.config import get_settings

logger = logging.getLogger("agent_kitkat.discovery_sources")
settings = get_settings()

# Strict Senior / Experienced exclusions
SENIOR_EXCLUDE_PATTERNS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\bstaff\b", r"\blead\b", r"\bprincipal\b",
    r"\barchitect\b", r"\bdirector\b", r"\bhead\b", r"\bvp\b", r"\bvice president\b",
    r"\bmanager\b", r"\bchief\b", r"\bexecutive\b", r"\btier\s*(?:ii|iii|iv|2|3|4)\b"
]

# Strict Intern / Fresher / Student inclusions
INTERN_INCLUDE_PATTERNS = [
    r"\bintern\b", r"\binternship\b", r"\bfresher\b", r"\bjunior\b", r"\bjr\.?\b",
    r"\bentry\s*-?level\b", r"\bgraduate\b", r"\bco-?op\b", r"\btrainee\b",
    r"\bapprentice\b", r"\bworking\s*student\b", r"\bwerkstudent\b", r"\bstudent\b", r"\bfellow\b"
]

# Geographic filters (India priority & Remote)
INDIA_LOCATION_PATTERNS = [
    r"\bindia\b", r"\bbangalore\b", r"\bbengaluru\b", r"\bdelhi\b",
    r"\bnoida\b", r"\bgurgaon\b", r"\bgurugram\b", r"\bhyderabad\b",
    r"\bpune\b", r"\bmumbai\b", r"\bchennai\b", r"\bkolkata\b", r"\bjaipur\b",
    r"\bahmedabad\b", r"\bkarnataka\b", r"\bmaharashtra\b", r"\bharyana\b"
]

REMOTE_LOCATION_PATTERNS = [
    r"\bremote\b", r"\bworldwide\b", r"\banywhere\b", r"\bwork from home\b", r"\bwfh\b"
]


class SourceFetchError(RuntimeError):
    """A discovery source could not be fetched (network error, HTTP error, bad payload)."""


def _client(timeout: float = 20.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, trust_env=settings.HTTP_TRUST_ENV, follow_redirects=True)


async def _get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    try:
        res = await client.get(url, **kwargs)
    except httpx.HTTPError as e:
        raise SourceFetchError(f"{type(e).__name__}: {e}") from e
    if res.status_code != 200:
        raise SourceFetchError(f"HTTP {res.status_code} from {url}")
    return res


def _parse_date(value: Any) -> Optional[str]:
    """Normalise epoch seconds / ISO-8601 / RFC-822 dates to ISO-8601 UTC. None if absent or unparseable."""
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        text = str(value).strip()
        if text.isdigit():
            return datetime.fromtimestamp(float(text), tz=timezone.utc).isoformat()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def _str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def is_senior_role(title: str) -> bool:
    """Check if title contains senior/lead/staff/architect keywords."""
    t = title.lower()
    return any(re.search(pat, t) for pat in SENIOR_EXCLUDE_PATTERNS)


def is_intern_or_fresher_role(title: str, text: str = "") -> bool:
    """Check if role is specifically intended for interns, students, or freshers."""
    if is_senior_role(title):
        return False
    t = title.lower()
    if any(re.search(pat, t) for pat in INTERN_INCLUDE_PATTERNS):
        return True
    t_text = text.lower()[:600]
    if any(k in t_text for k in [
        "internship", "intern role", "summer intern", "working student",
        "werkstudent", "0-1 year", "freshers", "entry level", "entry-level"
    ]):
        return True
    return False


# Remote regions an India-based candidate can actually work from
OPEN_REMOTE_REGIONS = {
    "", "worldwide", "anywhere", "global", "globally", "world", "international", "apac", "asia",
    "asia pacific", "south asia", "anywhere in the world", "the world", "remote",
}
_REMOTE_FILLER = re.compile(r"\b(?:remote|fully|100%|only|in|from|the|based|work from home|wfh|friendly|first|ok|role|position)\b|[()\-–:/]")


def classify_location(location_str: str, work_mode: str = "") -> Tuple[str, str]:
    """
    Classify where a job can be done from, for an India-based candidate.
    Returns (category, detail) with category one of:
      "india"             - located in India, or remote open to India
      "open_remote"       - remote with no country restriction (worldwide / anywhere / unqualified)
      "restricted_remote" - explicitly remote but limited to other countries (e.g. "Remote in USA", "Remote - Europe")
      "remote_region_unclear" - a remote role whose location field names another country/city without
                            saying whether remote work from India is allowed (e.g. "Berlin" + remote flag)
      "foreign"           - onsite/hybrid outside India
      "unknown"           - no usable location information
    """
    loc = (location_str or "").lower().strip()
    mode_remote = (work_mode or "").lower() == "remote"
    if not loc or loc in ("not stated", "not specified", "unknown", "n/a"):
        return ("open_remote", "remote, region not stated") if mode_remote else ("unknown", "location not stated")

    parts = [p.strip() for p in re.split(r"[,;|\n]|\s/\s", loc) if p.strip()]
    found_open = found_restricted = found_unclear = found_foreign = None
    for part in parts:
        if any(re.search(pat, part) for pat in INDIA_LOCATION_PATTERNS):
            return "india", part
        has_remote_word = any(re.search(pat, part) for pat in REMOTE_LOCATION_PATTERNS)
        if has_remote_word or mode_remote:
            residual = re.sub(r"\s+", " ", _REMOTE_FILLER.sub(" ", part)).strip(" .")
            if residual in OPEN_REMOTE_REGIONS or "worldwide" in residual or "anywhere" in residual:
                found_open = found_open or part
            elif has_remote_word:
                found_restricted = found_restricted or part
            else:
                found_unclear = found_unclear or part
        else:
            found_foreign = found_foreign or part
    if found_open:
        return "open_remote", found_open
    if found_restricted:
        return "restricted_remote", found_restricted
    if found_unclear:
        return "remote_region_unclear", found_unclear
    return "foreign", found_foreign or loc


def is_geographically_eligible(location_str: str, work_mode: str = "", text: str = "") -> tuple[bool, bool]:
    """
    Returns (is_eligible, is_india):
    - India location (or remote open to India) -> eligible, is_india=True
    - Remote with no country restriction -> eligible, is_india=False
    - Remote restricted to other countries, or foreign onsite/hybrid -> not eligible
    (`text` is accepted for backwards compatibility and ignored: location fields decide.)
    """
    category, _ = classify_location(location_str, work_mode)
    if category == "india":
        return True, True
    if category == "open_remote":
        return True, False
    return False, False


class BaseDiscoverySource:
    """Abstract base class for all job discovery sources."""
    name: str = "base"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError


class TechInternshipsDiscoverySource(BaseDiscoverySource):
    """
    SimplifyJobs / Pitt CSC community-maintained internship & new-grad listings (public JSON on GitHub).
    Mostly US roles: only India roles and explicitly remote roles are kept.
    NOTE: the internships repository is named per season; override the URL with
    SIMPLIFY_INTERNSHIPS_URL / SIMPLIFY_NEW_GRAD_URL env vars when a new season starts.
    """
    name = "simplify_internships"
    INTERNSHIPS_URL = os.getenv(
        "SIMPLIFY_INTERNSHIPS_URL",
        "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/.github/scripts/listings.json",
    )
    NEW_GRAD_URL = os.getenv(
        "SIMPLIFY_NEW_GRAD_URL",
        "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
    )

    def parse(self, data: List[Dict[str, Any]], is_internship_feed: bool) -> List[Dict[str, Any]]:
        india_results: List[Dict[str, Any]] = []
        remote_results: List[Dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict) or not item.get("active", True) or item.get("is_visible") is False:
                continue
            title = _str_or_none(item.get("title"))
            company = _str_or_none(item.get("company_name"))
            url = _str_or_none(item.get("url"))
            if not url or not title or not company:
                continue
            if is_senior_role(title):
                continue

            title_lower = title.lower()
            is_tech = any(k in title_lower for k in [
                "software", "developer", "engineer", "data", "ai",
                "machine learning", "frontend", "backend", "full stack",
                "cloud", "security", "web", "systems", "research"
            ])
            if not is_tech:
                continue
            is_early_career = is_internship_feed or any(k in title_lower for k in [
                "intern", "co-op", "fellow", "student", "junior", "trainee", "associate", "graduate", "new grad"
            ])
            if not is_early_career:
                continue

            locs = item.get("locations", [])
            loc_str = ", ".join(str(l) for l in locs) if isinstance(locs, list) else (_str_or_none(locs) or "")
            is_eligible, is_india = is_geographically_eligible(loc_str)
            if not is_eligible:
                continue
            is_remote = any(re.search(pat, loc_str.lower()) for pat in REMOTE_LOCATION_PATTERNS)

            degrees = item.get("degrees") or []
            facts = [f"{title} at {company}", f"Locations: {loc_str or 'not stated'}"]
            if degrees:
                facts.append(f"Degrees listed: {', '.join(str(d) for d in degrees)}")
            if item.get("category"):
                facts.append(f"Category: {item.get('category')}")
            if item.get("sponsorship"):
                facts.append(f"Sponsorship: {item.get('sponsorship')}")

            job_dict = {
                "title": title,
                "company": company,
                "url": url,
                "description": "",  # this feed carries no job description; analyse the URL for details
                "raw_text": "\n".join(facts),
                "location": loc_str or None,
                "work_mode": "Remote" if is_remote else "Unknown",
                "employment_type": "Internship" if is_internship_feed else None,
                "source": self.name,
                "job_id_external": _str_or_none(item.get("id")),
                "salary_stipend": None,
                "posted_at": _parse_date(item.get("date_posted")),
            }
            (india_results if is_india else remote_results).append(job_dict)
        return india_results + remote_results

    async def search(self, keywords: List[str], locations: List[str], limit: int = 12) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        errors: List[str] = []
        async with _client(30.0) as client:
            for target_url, is_internship_feed in ((self.INTERNSHIPS_URL, True), (self.NEW_GRAD_URL, False)):
                try:
                    res = await _get(client, target_url)
                    data = res.json()
                    if not isinstance(data, list):
                        raise SourceFetchError("Unexpected payload (expected a JSON list)")
                    results.extend(self.parse(data, is_internship_feed))
                except (SourceFetchError, ValueError) as e:
                    errors.append(f"{target_url}: {e}")
                    logger.warning("Simplify feed %s failed: %s", target_url, e)
        if errors and not results:
            raise SourceFetchError("; ".join(errors))
        # India first, then international remote
        results.sort(key=lambda j: 0 if is_geographically_eligible(j.get("location") or "")[1] else 1)
        return results[:limit]


class ArbeitnowDiscoverySource(BaseDiscoverySource):
    """
    Arbeitnow public job board API (https://www.arbeitnow.com/api/job-board-api).
    Kept: intern / working-student / junior tech roles located in India or flagged remote.
    """
    name = "arbeitnow"
    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    def parse(self, jobs: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for j in jobs:
            title = _str_or_none(j.get("title"))
            company = _str_or_none(j.get("company_name"))
            url = _str_or_none(j.get("url"))
            if not title or not company or not url:
                continue
            clean_desc = BeautifulSoup(j.get("description") or "", "html.parser").get_text(separator="\n").strip()
            if is_senior_role(title) or not is_intern_or_fresher_role(title, clean_desc):
                continue
            loc = _str_or_none(j.get("location")) or ""
            is_remote = bool(j.get("remote")) or any(re.search(p, loc.lower()) for p in REMOTE_LOCATION_PATTERNS)
            # Arbeitnow's "location" is the office city; a remote flag alone does not say which
            # countries may apply, so the listing is kept and eligibility flags the region as UNKNOWN.
            category, _ = classify_location(loc, "Remote" if is_remote else "")
            if category not in ("india", "open_remote", "remote_region_unclear"):
                continue
            title_lower = title.lower()
            if not any(k in title_lower for k in [
                "developer", "software", "engineer", "python", "data", "intern",
                "web", "frontend", "backend", "full stack", "ai", "machine learning"
            ]):
                continue
            job_types = j.get("job_types") or []
            results.append({
                "title": title,
                "company": company,
                "url": url,
                "description": clean_desc[:5000],
                "raw_text": f"{title} at {company}\nLocation: {loc or 'not stated'}\nRemote: {'yes' if j.get('remote') else 'not stated'}\n\n{clean_desc[:4000]}",
                "location": loc or None,
                "work_mode": "Remote" if is_remote else "Unknown",
                "employment_type": ", ".join(job_types) if job_types else None,
                "source": self.name,
                "job_id_external": _str_or_none(j.get("slug")),
                "salary_stipend": None,
                "posted_at": _parse_date(j.get("created_at")),
            })
            if len(results) >= limit:
                break
        return results

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        async with _client(20.0) as client:
            res = await _get(client, self.BASE_URL)
            try:
                jobs = res.json().get("data", [])
            except ValueError as e:
                raise SourceFetchError(f"Invalid JSON: {e}") from e
        results = self.parse(jobs, limit)
        logger.info("Arbeitnow: %d matching listings.", len(results))
        return results


def _format_salary(min_v: Any, max_v: Any, currency: Any, period: Any = None) -> Optional[str]:
    if min_v in (None, "", 0) and max_v in (None, "", 0):
        return None
    cur = f"{currency} " if currency else ""
    rng = f"{min_v}-{max_v}" if min_v and max_v and min_v != max_v else f"{min_v or max_v}"
    per = f" per {period}" if period else ""
    return f"{cur}{rng}{per}"


class JobicyDiscoverySource(BaseDiscoverySource):
    """Jobicy public remote-jobs API (https://jobicy.com/api/v2/remote-jobs). All listings are remote."""
    name = "jobicy"
    BASE_URL = "https://jobicy.com/api/v2/remote-jobs"

    def parse(self, jobs: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for j in jobs:
            title = _str_or_none(j.get("jobTitle"))
            company = _str_or_none(j.get("companyName"))
            url = _str_or_none(j.get("url"))
            if not title or not company or not url or is_senior_role(title):
                continue
            title_lower = title.lower()
            is_tech = any(k in title_lower for k in [
                "developer", "software", "engineer", "python", "data", "intern",
                "web", "frontend", "backend", "full stack", "ai", "cloud", "qa"
            ])
            is_non_tech = any(bad in title_lower for bad in [
                "sales", "account executive", "recruiter", "customer service", "telesales", "bdr", "sdr", "marketer"
            ])
            if not is_tech or is_non_tech:
                continue
            clean_desc = BeautifulSoup(j.get("jobDescription") or "", "html.parser").get_text(separator="\n").strip()
            level = _str_or_none(j.get("jobLevel"))
            if level and is_senior_role(level):
                continue
            geo = _str_or_none(j.get("jobGeo"))
            if not is_geographically_eligible(geo or "", "Remote")[0]:
                continue
            job_type = j.get("jobType")
            results.append({
                "title": title,
                "company": company,
                "url": url,
                "description": clean_desc[:5000],
                "raw_text": f"{title} at {company}\nLocation: {geo or 'not stated'} (Remote)\nLevel: {level or 'not stated'}\n\n{clean_desc[:4000]}",
                "location": geo,
                "work_mode": "Remote",
                "employment_type": ", ".join(job_type) if isinstance(job_type, list) else _str_or_none(job_type),
                "source": self.name,
                "job_id_external": _str_or_none(j.get("id")),
                "salary_stipend": _format_salary(j.get("annualSalaryMin"), j.get("annualSalaryMax"), j.get("salaryCurrency"), "year"),
                "posted_at": _parse_date(j.get("pubDate")),
            })
            if len(results) >= limit:
                break
        return results

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        async with _client(20.0) as client:
            res = await _get(client, self.BASE_URL, params={"count": min(limit * 4, 50), "tag": "entry-level"})
            try:
                jobs = res.json().get("jobs", [])
            except ValueError as e:
                raise SourceFetchError(f"Invalid JSON: {e}") from e
        results = self.parse(jobs, limit)
        logger.info("Jobicy: %d matching listings.", len(results))
        return results


class RemotiveDiscoverySource(BaseDiscoverySource):
    """Remotive public API (https://remotive.com/api/remote-jobs). All listings are remote."""
    name = "remotive"
    BASE_URL = "https://remotive.com/api/remote-jobs"

    def parse(self, jobs: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for j in jobs:
            title = _str_or_none(j.get("title"))
            company = _str_or_none(j.get("company_name"))
            url = _str_or_none(j.get("url"))
            if not title or not company or not url:
                continue
            clean_desc = BeautifulSoup(j.get("description") or "", "html.parser").get_text(separator="\n").strip()
            if is_senior_role(title) or not is_intern_or_fresher_role(title, clean_desc):
                continue
            title_lower = title.lower()
            is_tech = any(k in title_lower for k in [
                "developer", "software", "engineer", "python", "data", "intern",
                "web", "frontend", "backend", "full stack", "ai"
            ])
            is_non_tech = any(bad in title_lower for bad in [
                "content creator", "office assistant", "customer service", "sales", "marketing", "recruiter"
            ])
            if not is_tech or is_non_tech:
                continue
            loc = _str_or_none(j.get("candidate_required_location"))
            if not is_geographically_eligible(loc or "", "Remote")[0]:
                continue  # e.g. "USA Only": remote, but not open to candidates in India
            results.append({
                "title": title,
                "company": company,
                "url": url,
                "description": clean_desc[:5000],
                "raw_text": f"{title} at {company}\nCandidate location: {loc or 'not stated'} (Remote)\n\n{clean_desc[:4000]}",
                "location": loc,
                "work_mode": "Remote",
                "employment_type": _str_or_none(j.get("job_type")),
                "source": self.name,
                "job_id_external": _str_or_none(j.get("id")),
                "salary_stipend": _str_or_none(j.get("salary")),
                "posted_at": _parse_date(j.get("publication_date")),
            })
            if len(results) >= limit:
                break
        return results

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        async with _client(20.0) as client:
            res = await _get(client, self.BASE_URL, params={"category": "software-dev", "limit": limit * 10})
            try:
                jobs = res.json().get("jobs", [])
            except ValueError as e:
                raise SourceFetchError(f"Invalid JSON: {e}") from e
        results = self.parse(jobs, limit)
        logger.info("Remotive: %d matching listings.", len(results))
        return results


class WeWorkRemotelyDiscoverySource(BaseDiscoverySource):
    """We Work Remotely public RSS feed (programming category). All listings are remote."""
    name = "weworkremotely"
    BASE_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

    def parse(self, xml_text: str, limit: int) -> List[Dict[str, Any]]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise SourceFetchError(f"Invalid RSS: {e}") from e
        results: List[Dict[str, Any]] = []
        for it in root.findall(".//item"):
            raw_title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            clean_desc = BeautifulSoup(it.findtext("description") or "", "html.parser").get_text(separator="\n").strip()
            if ":" not in raw_title or not link:
                continue  # WWR titles are "Company: Role"; without it we would have to guess the company
            company, job_title = (x.strip() for x in raw_title.split(":", 1))
            if not company or not job_title:
                continue
            if is_senior_role(job_title) or not is_intern_or_fresher_role(job_title, clean_desc):
                continue
            region = _str_or_none(it.findtext("region"))
            if not is_geographically_eligible(region or "", "Remote")[0]:
                continue
            results.append({
                "title": job_title,
                "company": company,
                "url": link,
                "description": clean_desc[:5000],
                "raw_text": f"{job_title} at {company}\nRegion: {region or 'not stated'} (Remote)\n\n{clean_desc[:4000]}",
                "location": region,
                "work_mode": "Remote",
                "employment_type": _str_or_none(it.findtext("type")),
                "source": self.name,
                "job_id_external": _str_or_none(it.findtext("guid")) or link.rstrip("/").split("/")[-1],
                "salary_stipend": None,
                "posted_at": _parse_date(it.findtext("pubDate")),
            })
            if len(results) >= limit:
                break
        return results

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        async with _client(20.0) as client:
            res = await _get(client, self.BASE_URL)
        results = self.parse(res.text, limit)
        logger.info("WeWorkRemotely: %d matching listings.", len(results))
        return results


class AdzunaDiscoverySource(BaseDiscoverySource):
    """
    Adzuna Job Search API (India). Optional: requires free ADZUNA_APP_ID / ADZUNA_APP_KEY.
    """
    name = "adzuna"
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"

    @staticmethod
    def is_configured() -> bool:
        return bool(os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"))

    def parse(self, jobs: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for j in jobs[:limit]:
            title = _str_or_none(j.get("title"))
            company = _str_or_none((j.get("company") or {}).get("display_name"))
            url = _str_or_none(j.get("redirect_url"))
            if not title or not company or not url or is_senior_role(title):
                continue
            loc = _str_or_none((j.get("location") or {}).get("display_name"))
            desc = _str_or_none(j.get("description")) or ""
            results.append({
                "title": title,
                "company": company,
                "url": url,
                "description": desc,
                "raw_text": f"{title} at {company}\nLocation: {loc or 'not stated'}\n\n{desc}",
                "location": loc,
                "work_mode": "Unknown",
                "employment_type": _str_or_none(j.get("contract_time")),
                "source": self.name,
                "job_id_external": _str_or_none(j.get("id")),
                "salary_stipend": _format_salary(j.get("salary_min"), j.get("salary_max"), "INR", "year")
                if not j.get("salary_is_predicted") or str(j.get("salary_is_predicted")) == "0" else None,
                "posted_at": _parse_date(j.get("created")),
            })
        return results

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        if not self.is_configured():
            return []
        params = {
            "app_id": os.getenv("ADZUNA_APP_ID"),
            "app_key": os.getenv("ADZUNA_APP_KEY"),
            "what": "software intern",
            "where": "India",
            "results_per_page": limit,
            "content-type": "application/json",
        }
        async with _client(20.0) as client:
            res = await _get(client, self.BASE_URL, params=params)
            try:
                jobs = res.json().get("results", [])
            except ValueError as e:
                raise SourceFetchError(f"Invalid JSON: {e}") from e
        results = self.parse(jobs, limit)
        logger.info("Adzuna: %d listings.", len(results))
        return results


# Registry of live public sources (India first, international only when remote)
DISCOVERY_SOURCES: List[BaseDiscoverySource] = [
    TechInternshipsDiscoverySource(),
    ArbeitnowDiscoverySource(),
    JobicyDiscoverySource(),
    RemotiveDiscoverySource(),
    WeWorkRemotelyDiscoverySource(),
    AdzunaDiscoverySource(),
]
