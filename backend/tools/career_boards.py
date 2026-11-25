"""
Agent KitKat - Company career-board sources (official public job-board APIs).

Many companies that hire interns/freshers in India publish their openings on Greenhouse, Lever
or Ashby. Each of these offers a documented, public, unauthenticated JSON API for its job boards:

  Greenhouse  GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
  Lever       GET https://api.lever.co/v0/postings/{site}?mode=json&skip=N&limit=M
  Ashby       GET https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true

You choose which companies to follow (Settings -> Career boards) by pasting their careers URL,
e.g. https://boards.greenhouse.io/acme, https://jobs.lever.co/acme, https://jobs.ashbyhq.com/acme.
No company list is hardcoded.

Because each API returns the company's COMPLETE list of open jobs, a stored job from that board
that no longer appears has been taken down: it is reported as expired (snapshot evidence).
"""

import html
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from backend.tools.http_fetch import SourceFetchError, fetch, make_client
from backend.tools.job_discovery_sources import (
    BaseDiscoverySource,
    _parse_date,
    _str_or_none,
    classify_location,
    is_intern_or_fresher_role,
    is_senior_role,
)

logger = logging.getLogger("agent_kitkat.career_boards")

SUPPORTED_ATS = ("greenhouse", "lever", "ashby")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")

TECH_KEYWORDS = [
    "software", "developer", "engineer", "engineering", "sde", "data", "ai", "ml", "machine learning",
    "frontend", "front-end", "backend", "back-end", "full stack", "fullstack", "python", "java",
    "react", "web", "cloud", "devops", "security", "qa", "test", "mobile", "android", "ios", "research",
]


def parse_board_url(url_or_token: str, ats: Optional[str] = None) -> Tuple[str, str]:
    """
    Turn a careers URL (or a bare token + ats) into (ats, token).
    Raises ValueError for anything that is not a recognisable public board.
    """
    value = (url_or_token or "").strip()
    if ats:
        ats = ats.lower().strip()
        if ats not in SUPPORTED_ATS:
            raise ValueError(f"Unsupported job board '{ats}'. Supported: {', '.join(SUPPORTED_ATS)}.")
        if not _TOKEN_RE.match(value):
            raise ValueError("Board name may only contain letters, digits, '-', '_' and '.'.")
        return ats, value

    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]
    token = None
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io", "job-boards.eu.greenhouse.io"):
        ats, token = "greenhouse", (parts[0] if parts else None)
        if token == "embed":  # boards.greenhouse.io/embed/job_board?for=acme
            q = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
            token = q.get("for")
    elif host == "boards-api.greenhouse.io" and len(parts) >= 3 and parts[1] == "boards":
        ats, token = "greenhouse", parts[2]
    elif host in ("jobs.lever.co", "jobs.eu.lever.co"):
        ats, token = "lever", (parts[0] if parts else None)
    elif host in ("api.lever.co", "api.eu.lever.co") and len(parts) >= 3:
        ats, token = "lever", parts[2]
    elif host == "jobs.ashbyhq.com":
        ats, token = "ashby", (parts[0] if parts else None)
    elif host == "api.ashbyhq.com" and len(parts) >= 3:
        ats, token = "ashby", parts[-1]
    if not ats or not token or not _TOKEN_RE.match(token):
        raise ValueError(
            "Not a recognised public career board URL. Use a link like https://boards.greenhouse.io/<company>, "
            "https://jobs.lever.co/<company> or https://jobs.ashbyhq.com/<company>."
        )
    return ats, token


def _keep(title: str, text: str, location: str, work_mode: str, is_intern_type: bool = False) -> bool:
    if not title or is_senior_role(title):
        return False
    t = title.lower()
    if not any(k in t for k in TECH_KEYWORDS):
        return False
    if not (is_intern_type or is_intern_or_fresher_role(title, text)):
        return False
    category, _ = classify_location(location, work_mode)
    return category in ("india", "open_remote", "remote_region_unclear", "unknown")


class CareerBoardSource(BaseDiscoverySource):
    """One company's public career board."""

    ats: str = ""

    def __init__(self, token: str, company: Optional[str] = None):
        super().__init__()
        self.token = token
        self.company = (company or "").strip() or token
        self.name = f"{self.ats}:{token}"
        self.description = f"{self.company} careers ({self.ats.title()} public job-board API)"

    def ext_id(self, raw_id: Any) -> Optional[str]:
        raw = _str_or_none(raw_id)
        return f"{self.token}:{raw}" if raw else None

    def _finish(self, all_ids: set, results: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        # The board returned every open job: anything stored from this board but missing is closed.
        self.snapshot_scope = f"{self.token}:"
        self.snapshot_ids = all_ids
        logger.info("%s: %d open jobs, %d matching.", self.name, len(all_ids), len(results))
        return results[:limit]


class GreenhouseBoardSource(CareerBoardSource):
    ats = "greenhouse"

    def parse(self, payload: Dict[str, Any]) -> Tuple[set, List[Dict[str, Any]]]:
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            raise SourceFetchError("Unexpected Greenhouse payload (no 'jobs' list)")
        all_ids, results = set(), []
        for j in jobs:
            ext = self.ext_id(j.get("id"))
            if ext:
                all_ids.add(ext)
            title = _str_or_none(j.get("title"))
            url = _str_or_none(j.get("absolute_url"))
            loc = _str_or_none((j.get("location") or {}).get("name")) or ""
            desc = BeautifulSoup(html.unescape(j.get("content") or ""), "html.parser").get_text("\n").strip()
            if not title or not url or not ext:
                continue
            work_mode = "Remote" if re.search(r"\bremote\b", loc.lower()) else "Unknown"
            if not _keep(title, desc, loc, work_mode):
                continue
            depts = ", ".join(d.get("name", "") for d in (j.get("departments") or []) if d.get("name"))
            results.append({
                "title": title, "company": self.company, "url": url,
                "description": desc[:5000],
                "raw_text": f"{title} at {self.company}\nLocation: {loc or 'not stated'}\n"
                            + (f"Department: {depts}\n" if depts else "") + f"\n{desc[:4000]}",
                "location": loc or None, "work_mode": work_mode, "employment_type": None,
                "source": self.name, "job_id_external": ext, "salary_stipend": None,
                # Greenhouse's list API has updated_at but no publish date; we do not relabel one as the other.
                "posted_at": None,
            })
        return all_ids, results

    async def search(self, keywords, locations, limit: int = 10) -> List[Dict[str, Any]]:
        async with make_client(30.0) as client:
            res = await fetch(client, f"https://boards-api.greenhouse.io/v1/boards/{self.token}/jobs", params={"content": "true"})
        try:
            payload = res.json()
        except ValueError as e:
            raise SourceFetchError(f"Invalid JSON: {e}") from e
        all_ids, results = self.parse(payload)
        return self._finish(all_ids, results, limit)


class LeverBoardSource(CareerBoardSource):
    ats = "lever"
    PAGE = 100
    MAX_PAGES = 10

    def parse(self, postings: List[Dict[str, Any]]) -> Tuple[set, List[Dict[str, Any]]]:
        all_ids, results = set(), []
        for j in postings:
            ext = self.ext_id(j.get("id"))
            if ext:
                all_ids.add(ext)
            title = _str_or_none(j.get("text"))
            url = _str_or_none(j.get("hostedUrl")) or _str_or_none(j.get("applyUrl"))
            cats = j.get("categories") or {}
            locs = cats.get("allLocations") or ([cats.get("location")] if cats.get("location") else [])
            loc = ", ".join(str(l) for l in locs if l)
            wpt = (j.get("workplaceType") or "").lower()
            work_mode = {"remote": "Remote", "hybrid": "Hybrid", "on-site": "Onsite"}.get(wpt, "Unknown")
            commitment = _str_or_none(cats.get("commitment"))
            desc = (j.get("descriptionPlain") or "").strip()
            if not title or not url or not ext:
                continue
            is_intern_type = bool(commitment and re.search(r"intern", commitment.lower()))
            if not _keep(title, desc, loc, work_mode, is_intern_type):
                continue
            results.append({
                "title": title, "company": self.company, "url": url,
                "description": desc[:5000],
                "raw_text": f"{title} at {self.company}\nLocation: {loc or 'not stated'}\nWorkplace: {work_mode}\n"
                            + (f"Commitment: {commitment}\n" if commitment else "") + f"\n{desc[:4000]}",
                "location": loc or None, "work_mode": work_mode, "employment_type": commitment,
                "source": self.name, "job_id_external": ext, "salary_stipend": None,
                "posted_at": None,  # createdAt is not part of Lever's documented posting fields
            })
        return all_ids, results

    async def search(self, keywords, locations, limit: int = 10) -> List[Dict[str, Any]]:
        postings: List[Dict[str, Any]] = []
        async with make_client(30.0) as client:
            for page in range(self.MAX_PAGES):
                res = await fetch(client, f"https://api.lever.co/v0/postings/{self.token}",
                                  params={"mode": "json", "skip": page * self.PAGE, "limit": self.PAGE})
                try:
                    batch = res.json()
                except ValueError as e:
                    raise SourceFetchError(f"Invalid JSON: {e}") from e
                if not isinstance(batch, list):
                    raise SourceFetchError("Unexpected Lever payload (expected a list)")
                postings.extend(batch)
                if len(batch) < self.PAGE:
                    break
            else:
                # Not a complete snapshot: do not use it to expire anything
                all_ids, results = self.parse(postings)
                return results[:limit]
        all_ids, results = self.parse(postings)
        return self._finish(all_ids, results, limit)


class AshbyBoardSource(CareerBoardSource):
    ats = "ashby"

    def parse(self, payload: Dict[str, Any]) -> Tuple[set, List[Dict[str, Any]]]:
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            raise SourceFetchError("Unexpected Ashby payload (no 'jobs' list)")
        all_ids, results = set(), []
        for j in jobs:
            if j.get("isListed") is False:
                continue
            ext = self.ext_id(j.get("id") or j.get("jobUrl"))
            if ext:
                all_ids.add(ext)
            title = _str_or_none(j.get("title"))
            url = _str_or_none(j.get("jobUrl")) or _str_or_none(j.get("applyUrl"))
            locs = [j.get("location")] + [s.get("location") for s in (j.get("secondaryLocations") or []) if isinstance(s, dict)]
            loc = ", ".join(str(l) for l in locs if l)
            wpt = (j.get("workplaceType") or "").lower()
            work_mode = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "Onsite"}.get(wpt, "Unknown")
            emp = _str_or_none(j.get("employmentType"))
            desc = (j.get("descriptionPlain") or "").strip()
            if not title or not url or not ext:
                continue
            if not _keep(title, desc, loc, work_mode, is_intern_type=(emp == "Intern")):
                continue
            comp = j.get("compensation") or {}
            results.append({
                "title": title, "company": self.company, "url": url,
                "description": desc[:5000],
                "raw_text": f"{title} at {self.company}\nLocation: {loc or 'not stated'}\nWorkplace: {work_mode}\n"
                            + (f"Employment type: {emp}\n" if emp else "") + f"\n{desc[:4000]}",
                "location": loc or None, "work_mode": work_mode, "employment_type": emp,
                "source": self.name, "job_id_external": ext,
                "salary_stipend": _str_or_none(comp.get("compensationTierSummary")) if isinstance(comp, dict) else None,
                "posted_at": _parse_date(j.get("publishedAt")),
            })
        return all_ids, results

    async def search(self, keywords, locations, limit: int = 10) -> List[Dict[str, Any]]:
        async with make_client(30.0) as client:
            res = await fetch(client, f"https://api.ashbyhq.com/posting-api/job-board/{self.token}",
                              params={"includeCompensation": "true"})
        try:
            payload = res.json()
        except ValueError as e:
            raise SourceFetchError(f"Invalid JSON: {e}") from e
        all_ids, results = self.parse(payload)
        return self._finish(all_ids, results, limit)


_BOARD_CLASSES = {"greenhouse": GreenhouseBoardSource, "lever": LeverBoardSource, "ashby": AshbyBoardSource}


def build_board_sources(boards: List[Dict[str, Any]]) -> List[CareerBoardSource]:
    """Build sources from the stored list [{"ats": ..., "token": ..., "company": ..., "enabled": bool}]."""
    sources: List[CareerBoardSource] = []
    for b in boards or []:
        if not isinstance(b, dict) or b.get("enabled") is False:
            continue
        cls = _BOARD_CLASSES.get(str(b.get("ats", "")).lower())
        token = str(b.get("token", ""))
        if cls and _TOKEN_RE.match(token):
            sources.append(cls(token, b.get("company")))
    return sources
