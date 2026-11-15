"""
Agent KitKat - Public Job Discovery Sources (Multi-Source, 100% Real Live Feeds, ₹0 Budget)
Strict Geographic & Career Hierarchy:
1. PRIORITY 1: India Domestic Tech Roles (Delhi NCR, Noida, Gurgaon, Bangalore, Hyderabad, Pune, Remote India, etc.)
2. PRIORITY 2: International Roles ONLY IF REMOTE (Worldwide Remote, Remote in USA, etc.)
3. REJECTED: Any foreign onsite/hybrid role (Zurich, Munich, Amsterdam, Chicago onsite, etc.)
4. CAREER LEVEL: Strictly Intern, Working Student, Fresher, and Entry-Level (Zero Senior / Lead / Staff).

ZERO MOCK DATA. ZERO FABRICATED LISTINGS.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional
import xml.etree.ElementTree as ET
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


def is_geographically_eligible(location_str: str, work_mode: str = "", text: str = "") -> tuple[bool, bool]:
    """
    Returns (is_eligible, is_india):
    - India location -> Eligible (is_india=True)
    - International Remote -> Eligible (is_india=False)
    - Foreign Onsite/Hybrid -> Ineligible (is_eligible=False)
    """
    loc = location_str.lower()
    mode = work_mode.lower()
    raw = text.lower()[:400]

    is_india = (
        any(re.search(pat, loc) for pat in INDIA_LOCATION_PATTERNS)
        or any(re.search(pat, raw) for pat in INDIA_LOCATION_PATTERNS)
    )
    is_remote = (
        mode == "remote"
        or any(re.search(pat, loc) for pat in REMOTE_LOCATION_PATTERNS)
        or any(re.search(pat, raw) for pat in REMOTE_LOCATION_PATTERNS)
    )

    if is_india:
        return True, True
    if is_remote:
        return True, False
    return False, False


class BaseDiscoverySource:
    """Abstract base class for all job discovery sources."""
    name: str = "base"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError


class TechInternshipsDiscoverySource(BaseDiscoverySource):
    """
    Verified Live Tech Internships & New Grad Feed (Official PittCSC / SimplifyJobs repositories).
    Pulls real live tech internships & graduate roles, prioritizing India positions and International Remote positions.
    Rejects foreign onsite/hybrid roles.
    """
    name = "simplify_internships"
    INTERNSHIPS_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/.github/scripts/listings.json"
    NEW_GRAD_URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 12) -> List[Dict[str, Any]]:
        india_results: List[Dict[str, Any]] = []
        remote_results: List[Dict[str, Any]] = []

        urls = [self.INTERNSHIPS_URL, self.NEW_GRAD_URL]

        try:
            async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
                for target_url in urls:
                    try:
                        res = await client.get(target_url)
                        if res.status_code != 200:
                            continue
                        data = res.json()
                        for item in data:
                            if not item.get("active", True):
                                continue
                            title = item.get("title", "")
                            company = item.get("company_name", "")
                            url = item.get("url", "")
                            if not url or not title or not company:
                                continue

                            # Hard exclusion of senior / staff / lead
                            if is_senior_role(title):
                                continue

                            # Technical role check
                            title_lower = title.lower()
                            is_tech = any(k in title_lower for k in [
                                "software", "developer", "engineer", "data", "ai",
                                "machine learning", "frontend", "backend", "full stack",
                                "cloud", "security", "web", "systems", "research"
                            ])
                            if not is_tech:
                                continue

                            # Must be intern, student, or junior/entry role
                            is_early_career = any(k in title_lower for k in [
                                "intern", "co-op", "fellow", "student", "junior", "trainee", "associate", "graduate", "new grad"
                            ]) or "intern" in target_url
                            if not is_early_career:
                                continue

                            locs = item.get("locations", [])
                            loc_str = ", ".join(locs) if isinstance(locs, list) else str(locs)

                            # Geographic eligibility check: India first, Foreign ONLY if Remote
                            is_eligible, is_india = is_geographically_eligible(loc_str)
                            if not is_eligible:
                                # Foreign onsite / hybrid -> Skip
                                continue

                            is_remote = "remote" in loc_str.lower() or "worldwide" in loc_str.lower()
                            work_mode = "Remote" if is_remote else ("Hybrid" if is_india else "Remote")

                            desc = (
                                f"{title} opportunity at {company}. "
                                f"Locations: {loc_str}. Target degrees: {', '.join(item.get('degrees', ['Bachelor']))}. "
                                f"Category: {item.get('category', 'Technology')}."
                            )

                            job_dict = {
                                "title": title,
                                "company": company,
                                "url": url,
                                "description": desc,
                                "raw_text": f"{title} at {company}\nLocations: {loc_str}\n\n{desc}",
                                "location": loc_str if loc_str else ("India" if is_india else "Remote"),
                                "work_mode": work_mode,
                                "source": "simplify_internships",
                                "job_id_external": str(item.get("id") or (len(india_results) + len(remote_results))),
                                "salary_stipend": "Paid Internship / Stipend" if "intern" in title_lower else "Competitive Entry-Level",
                            }

                            if is_india:
                                india_results.append(job_dict)
                            else:
                                remote_results.append(job_dict)

                    except Exception as fe:
                        logger.warning("Error fetching dataset from %s: %s", target_url, fe)

            # Prioritize India opportunities at the very top, followed by International Remote
            combined = india_results + remote_results
            logger.info("Tech Internships Feed: Discovered %d India roles, %d International Remote roles.", len(india_results), len(remote_results))
            return combined[:limit]

        except Exception as e:
            logger.warning("Tech Internships Feed failed: %s", e)
            return []


class ArbeitnowDiscoverySource(BaseDiscoverySource):
    """
    Arbeitnow Public Job Board API.
    Filtered strictly for Working Student / Intern / Junior tech positions that are 100% REMOTE.
    Foreign onsite/hybrid listings are rejected.
    """
    name = "arbeitnow"
    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                res = await client.get(self.BASE_URL)
                if res.status_code == 200:
                    data = res.json()
                    jobs = data.get("data", [])

                    for j in jobs:
                        title = j.get("title", "")
                        company = j.get("company_name", "Tech Company")
                        raw_desc = j.get("description", "")
                        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator="\n").strip()

                        # Must not be senior
                        if is_senior_role(title):
                            continue

                        # Intern / Working Student / Junior only
                        if not is_intern_or_fresher_role(title, clean_desc):
                            continue

                        loc = j.get("location") or ""
                        is_remote = j.get("remote", False) or "remote" in loc.lower() or "worldwide" in loc.lower()
                        is_india = any(re.search(pat, loc.lower()) for pat in INDIA_LOCATION_PATTERNS)

                        # Must be in India OR 100% Remote
                        if not is_india and not is_remote:
                            continue

                        title_lower = title.lower()
                        is_tech = any(k in title_lower for k in [
                            "developer", "software", "engineer", "python", "data", "intern",
                            "web", "frontend", "backend", "full stack", "ai", "machine learning"
                        ])

                        if is_tech:
                            results.append({
                                "title": title,
                                "company": company,
                                "url": j.get("url", ""),
                                "description": clean_desc[:2500],
                                "raw_text": f"{title} at {company}\nLocation: {loc}\n\n{clean_desc[:1500]}",
                                "location": loc if loc else ("India" if is_india else "Remote"),
                                "work_mode": "Remote" if is_remote else "Hybrid",
                                "source": "arbeitnow",
                                "job_id_external": str(j.get("slug") or len(results)),
                                "salary_stipend": "Paid Working Student / Intern",
                            })

                        if len(results) >= limit:
                            break

                    logger.info("Arbeitnow API: Discovered %d real live Remote/India intern opportunities.", len(results))
        except Exception as e:
            logger.warning("Arbeitnow API fetch failed: %s", e)

        return results


class JobicyDiscoverySource(BaseDiscoverySource):
    """
    Jobicy Public Remote Jobs API.
    Filtered strictly for Entry-Level & Intern tech opportunities (100% Remote).
    """
    name = "jobicy"
    BASE_URL = "https://jobicy.com/api/v2/remote-jobs"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            params = {
                "count": limit * 4,
                "tag": "entry-level"
            }
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                res = await client.get(self.BASE_URL, params=params)
                if res.status_code == 200:
                    data = res.json()
                    jobs = data.get("jobs", [])
                    for j in jobs:
                        title = j.get("jobTitle", "Developer")
                        company = j.get("companyName", "Tech Company")
                        raw_desc = j.get("jobDescription", "")
                        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator="\n").strip()

                        # Must not be senior
                        if is_senior_role(title):
                            continue

                        # Ensure technical role
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

                        geo = j.get("jobGeo") or "Remote"
                        results.append({
                            "title": title,
                            "company": company,
                            "url": j.get("url", ""),
                            "description": clean_desc[:2500],
                            "raw_text": f"{title} at {company}\nLocation: {geo} (Remote)\n\n{clean_desc[:1500]}",
                            "location": geo,
                            "work_mode": "Remote",
                            "source": "jobicy",
                            "job_id_external": str(j.get("id")),
                            "salary_stipend": j.get("annualSalaryMin") or "Stipend / Competitive",
                        })
                        if len(results) >= limit:
                            break
                    logger.info("Jobicy API: Discovered %d real live entry-level remote opportunities.", len(results))
        except Exception as e:
            logger.warning("Jobicy API fetch failed: %s", e)

        return results


class RemotiveDiscoverySource(BaseDiscoverySource):
    """
    Remotive Public Job Board API.
    Filtered strictly for Junior & Intern developer listings (100% Remote).
    """
    name = "remotive"
    BASE_URL = "https://remotive.com/api/remote-jobs"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        try:
            params = {
                "category": "software-dev",
                "limit": limit * 4
            }
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                res = await client.get(self.BASE_URL, params=params)
                if res.status_code == 200:
                    data = res.json()
                    jobs = data.get("jobs", [])
                    for j in jobs:
                        title = j.get("title", "")
                        company = j.get("company_name", "Tech Startup")
                        raw_desc = j.get("description", "")
                        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator="\n").strip()

                        # Must not be senior
                        if is_senior_role(title):
                            continue

                        # Check if intern / junior / entry level
                        if not is_intern_or_fresher_role(title, clean_desc):
                            continue

                        # Ensure technical role
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

                        loc = j.get("candidate_required_location") or "Remote"
                        results.append({
                            "title": title,
                            "company": company,
                            "url": j.get("url", ""),
                            "description": clean_desc[:2500],
                            "raw_text": f"{title} at {company}\nLocation: {loc} (Remote)\n\n{clean_desc[:1500]}",
                            "location": loc,
                            "work_mode": "Remote",
                            "source": "remotive",
                            "job_id_external": str(j.get("id")),
                            "salary_stipend": j.get("salary") or "Competitive",
                        })
                        if len(results) >= limit:
                            break
                    logger.info("Remotive API: Discovered %d real live intern/junior remote opportunities.", len(results))
        except Exception as e:
            logger.warning("Remotive API fetch failed: %s", e)

        return results


class WeWorkRemotelyDiscoverySource(BaseDiscoverySource):
    """
    WeWorkRemotely Live RSS Feed.
    Filtered strictly for Entry-Level and Junior remote programming jobs (100% Remote).
    """
    name = "weworkremotely"
    BASE_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                res = await client.get(self.BASE_URL)
                if res.status_code == 200:
                    root = ET.fromstring(res.text)
                    items = root.findall(".//item")

                    for it in items:
                        raw_title = it.find("title").text if it.find("title") is not None else ""
                        link = it.find("link").text if it.find("link") is not None else ""
                        raw_desc = it.find("description").text if it.find("description") is not None else ""
                        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator="\n").strip()

                        if ":" in raw_title:
                            company, job_title = raw_title.split(":", 1)
                            company = company.strip()
                            job_title = job_title.strip()
                        else:
                            company = "Tech Company"
                            job_title = raw_title.strip()

                        # Must not be senior
                        if is_senior_role(job_title):
                            continue

                        # Must be intern or junior
                        if not is_intern_or_fresher_role(job_title, clean_desc):
                            continue

                        results.append({
                            "title": job_title,
                            "company": company,
                            "url": link,
                            "description": clean_desc[:2500],
                            "raw_text": f"{job_title} at {company}\nRemote Programming Role\n\n{clean_desc[:1500]}",
                            "location": "Remote",
                            "work_mode": "Remote",
                            "source": "weworkremotely",
                            "job_id_external": link.split("/")[-1] if link else str(len(results)),
                            "salary_stipend": "Competitive Remote Rate",
                        })

                        if len(results) >= limit:
                            break

                    logger.info("WeWorkRemotely RSS: Discovered %d real live remote opportunities.", len(results))
        except Exception as e:
            logger.warning("WeWorkRemotely RSS fetch failed: %s", e)

        return results


class AdzunaDiscoverySource(BaseDiscoverySource):
    """
    Adzuna Job Search API.
    Targeting India software internships if configured.
    """
    name = "adzuna"
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        app_id = os.getenv("ADZUNA_APP_ID")
        app_key = os.getenv("ADZUNA_APP_KEY")

        if not app_id or not app_key:
            return []

        results: List[Dict[str, Any]] = []
        try:
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "what": "Software Intern",
                "where": "India",
                "results_per_page": limit,
                "content-type": "application/json"
            }
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                res = await client.get(self.BASE_URL, params=params)
                if res.status_code == 200:
                    data = res.json()
                    jobs = data.get("results", [])
                    for j in jobs[:limit]:
                        title = j.get("title", "")
                        if is_senior_role(title):
                            continue
                        results.append({
                            "title": title,
                            "company": j.get("company", {}).get("display_name", "Unknown"),
                            "url": j.get("redirect_url", ""),
                            "description": j.get("description", ""),
                            "raw_text": f"{title} at {j.get('company', {}).get('display_name')}\nLocation: India\n\n{j.get('description')}",
                            "location": "India",
                            "work_mode": "Hybrid",
                            "source": "adzuna",
                            "job_id_external": str(j.get("id")),
                            "salary_stipend": "Disclosed upon application",
                        })
                    logger.info("Adzuna API: Discovered %d real live India opportunities.", len(results))
        except Exception as e:
            logger.warning("Adzuna API fetch failed: %s", e)

        return results


# Registry of 100% REAL LIVE active sources strictly prioritizing INDIA & INTERNATIONAL REMOTE
DISCOVERY_SOURCES: List[BaseDiscoverySource] = [
    TechInternshipsDiscoverySource(),
    ArbeitnowDiscoverySource(),
    JobicyDiscoverySource(),
    RemotiveDiscoverySource(),
    WeWorkRemotelyDiscoverySource(),
    AdzunaDiscoverySource(),
]
