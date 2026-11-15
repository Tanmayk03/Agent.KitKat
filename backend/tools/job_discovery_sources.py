"""
Agent KitKat - Public Job Discovery Sources (Multi-Source, 100% Real Live Feeds, ₹0 Budget)
Integrates permitted real public job APIs and feeds:
1. Arbeitnow API (100% Free Public Tech Jobs Feed - Real live company postings worldwide)
2. WeWorkRemotely RSS (100% Free Public Programming Jobs Feed - Live real postings)
3. Remotive API (100% Free Public Tech Jobs Feed - Zero key required)
4. Jobicy API (100% Free Public Remote Developer Feed - Zero key required)
5. Adzuna API (Free Tier - Active if APP_ID / APP_KEY provided)

ZERO MOCK DATA. ZERO FABRICATED LISTINGS.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import xml.etree.ElementTree as ET
import httpx
from bs4 import BeautifulSoup

from backend.config import get_settings

logger = logging.getLogger("agent_kitkat.discovery_sources")
settings = get_settings()


class BaseDiscoverySource:
    """Abstract base class for all job discovery sources."""
    name: str = "base"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError


class ArbeitnowDiscoverySource(BaseDiscoverySource):
    """
    Arbeitnow Public Job Board API.
    Zero-cost, public access, live tech, developer, and engineering listings.
    """
    name = "arbeitnow"
    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        kw_lower = [k.lower() for k in keywords] if keywords else ["developer", "software", "engineer", "intern", "python", "data"]

        try:
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                res = await client.get(self.BASE_URL)
                if res.status_code == 200:
                    data = res.json()
                    jobs = data.get("data", [])

                    for j in jobs:
                        title = j.get("title", "")
                        company = j.get("company_name", "Tech Company")
                        tags = j.get("tags", [])
                        raw_desc = j.get("description", "")
                        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator="\n").strip()

                        # Strict relevance: Job title must be a genuine technical / engineering role
                        title_lower = title.lower()
                        is_tech = any(k in title_lower for k in ["developer", "software", "engineer", "python", "data", "intern", "web", "frontend", "backend", "full stack", "ai", "machine learning", "genai"])
                        is_non_tech = any(bad in title_lower for bad in ["sales", "account executive", "recruiter", "video", "content", "hr", "marketing", "office assistant", "ehrenamtliche", "sachbearbeiter", "customer service"])

                        if is_tech and not is_non_tech:
                            loc = j.get("location") or "Remote / Europe"
                            is_remote = j.get("remote", False) or "remote" in loc.lower()
                            results.append({
                                "title": title,
                                "company": company,
                                "url": j.get("url", ""),
                                "description": clean_desc[:2500],
                                "raw_text": f"{title} at {company}\nLocation: {loc}\n\n{clean_desc[:1500]}",
                                "location": loc,
                                "work_mode": "Remote" if is_remote else "Hybrid",
                                "source": "arbeitnow",
                                "job_id_external": str(j.get("slug") or len(results)),
                                "salary_stipend": "Disclosed upon application",
                            })

                        if len(results) >= limit:
                            break

                    logger.info("Arbeitnow API: Discovered %d real live opportunities.", len(results))
        except Exception as e:
            logger.warning("Arbeitnow API fetch failed: %s", e)

        return results


class WeWorkRemotelyDiscoverySource(BaseDiscoverySource):
    """
    WeWorkRemotely Live RSS Feed.
    Zero-cost, public RSS feed of real remote programming jobs.
    """
    name = "weworkremotely"
    BASE_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        kw_lower = [k.lower() for k in keywords] if keywords else ["developer", "software", "engineer", "python"]

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

                        # Format: "Company: Job Title"
                        if ":" in raw_title:
                            company, job_title = raw_title.split(":", 1)
                            company = company.strip()
                            job_title = job_title.strip()
                        else:
                            company = "Tech Company"
                            job_title = raw_title.strip()

                        full_text = f"{job_title} {company} {clean_desc[:500]}".lower()
                        is_relevant = any(k in full_text for k in kw_lower) or any(t in full_text for t in ["software", "developer", "engineer", "python", "data", "web"])

                        if is_relevant:
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

                    logger.info("WeWorkRemotely RSS: Discovered %d real live opportunities.", len(results))
        except Exception as e:
            logger.warning("WeWorkRemotely RSS fetch failed: %s", e)

        return results


class RemotiveDiscoverySource(BaseDiscoverySource):
    """
    Remotive Public Job Board API.
    Zero-cost, public access, developer & engineering listings.
    """
    name = "remotive"
    BASE_URL = "https://remotive.com/api/remote-jobs"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        try:
            params = {
                "category": "software-dev",
                "limit": limit * 2
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

                        # Ensure technical role
                        title_lower = title.lower()
                        is_tech = any(k in title_lower for k in ["developer", "software", "engineer", "python", "data", "intern", "web", "frontend", "backend", "full stack", "ai", "machine learning", "cloud", "devops"])
                        is_non_tech = any(bad in title_lower for bad in ["content creator", "office assistant", "customer service", "sales", "marketing", "recruiter", "account executive"])

                        if not is_tech or is_non_tech:
                            continue

                        results.append({
                            "title": title,
                            "company": company,
                            "url": j.get("url", ""),
                            "description": clean_desc[:2500],
                            "raw_text": f"{title} at {company}\nLocation: {j.get('candidate_required_location', 'Remote')}\n\n{clean_desc[:1500]}",
                            "location": j.get("candidate_required_location") or "Remote",
                            "work_mode": "Remote",
                            "source": "remotive",
                            "job_id_external": str(j.get("id")),
                            "salary_stipend": j.get("salary") or "Competitive",
                        })
                        if len(results) >= limit:
                            break
                    logger.info("Remotive API: Discovered %d real live opportunities.", len(results))
                else:
                    logger.warning("Remotive API returned status %d", res.status_code)
        except Exception as e:
            logger.warning("Remotive API fetch failed: %s", e)

        return results


class JobicyDiscoverySource(BaseDiscoverySource):
    """
    Jobicy Public Remote Jobs API.
    Zero-cost, public JSON feed for remote developers and engineers.
    """
    name = "jobicy"
    BASE_URL = "https://jobicy.com/api/v2/remote-jobs"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            params = {
                "count": limit,
                "tag": "developer"
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

                        # Ensure technical role
                        title_lower = title.lower()
                        is_tech = any(k in title_lower for k in ["developer", "software", "engineer", "python", "data", "intern", "web", "frontend", "backend", "full stack", "ai", "architect", "advocate", "cloud", "devops"])
                        is_non_tech = any(bad in title_lower for bad in ["sales", "account executive", "recruiter", "customer service"])

                        if not is_tech or is_non_tech:
                            continue

                        results.append({
                            "title": title,
                            "company": company,
                            "url": j.get("url", ""),
                            "description": clean_desc[:2500],
                            "raw_text": f"{title} at {company}\n\n{clean_desc[:1500]}",
                            "location": j.get("jobGeo") or "Remote",
                            "work_mode": "Remote",
                            "source": "jobicy",
                            "job_id_external": str(j.get("id")),
                            "salary_stipend": j.get("annualSalaryMin") or "Stipend / Competitive",
                        })
                        if len(results) >= limit:
                            break
                    logger.info("Jobicy API: Discovered %d real live opportunities.", len(results))
        except Exception as e:
            logger.warning("Jobicy API fetch failed: %s", e)

        return results


class AdzunaDiscoverySource(BaseDiscoverySource):
    """
    Adzuna Job Search API.
    Available if user configures free tier APP_ID and APP_KEY in environment.
    """
    name = "adzuna"
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"

    async def search(self, keywords: List[str], locations: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        app_id = os.getenv("ADZUNA_APP_ID")
        app_key = os.getenv("ADZUNA_APP_KEY")

        if not app_id or not app_key:
            return []

        results: List[Dict[str, Any]] = []
        try:
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "what": " ".join(keywords[:2]),
                "where": locations[0] if locations else "India",
                "results_per_page": limit,
                "content-type": "application/json"
            }
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                res = await client.get(self.BASE_URL, params=params)
                if res.status_code == 200:
                    data = res.json()
                    jobs = data.get("results", [])
                    for j in jobs[:limit]:
                        results.append({
                            "title": j.get("title", ""),
                            "company": j.get("company", {}).get("display_name", "Unknown"),
                            "url": j.get("redirect_url", ""),
                            "description": j.get("description", ""),
                            "raw_text": f"{j.get('title')} at {j.get('company', {}).get('display_name')}\n\n{j.get('description')}",
                            "location": j.get("location", {}).get("display_name", "India"),
                            "work_mode": "Hybrid",
                            "source": "adzuna",
                            "job_id_external": str(j.get("id")),
                            "salary_stipend": "Disclosed upon application",
                        })
                    logger.info("Adzuna API: Discovered %d real live opportunities.", len(results))
        except Exception as e:
            logger.warning("Adzuna API fetch failed: %s", e)

        return results


# Registry of 100% REAL LIVE active sources (ZERO fake or mock data)
DISCOVERY_SOURCES: List[BaseDiscoverySource] = [
    ArbeitnowDiscoverySource(),
    WeWorkRemotelyDiscoverySource(),
    RemotiveDiscoverySource(),
    JobicyDiscoverySource(),
    AdzunaDiscoverySource(),
]
