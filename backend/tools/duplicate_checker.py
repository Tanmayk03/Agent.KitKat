"""
Agent KitKat - Job Duplicate Detection Tool
Identifies previously discovered, analyzed, applied, or rejected jobs
using normalized company, title, URL, and external job ID matching.
Prevents duplicate applications and keeps discovery clean.
"""

import re
import urllib.parse
from typing import Optional, Tuple
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Job


class DuplicateChecker:
    """
    Intelligent duplicate detection across discovered opportunities.
    """

    @staticmethod
    def normalize_company(company: str) -> str:
        """Normalize company name by removing common business suffixes and punctuation."""
        if not company:
            return ""
        name = company.lower().strip()
        # Remove common business suffixes
        suffixes = [
            r"\binc\b", r"\bllc\b", r"\bltd\b", r"\bpvt\b", r"\bpvt ltd\b",
            r"\bcorp\b", r"\bcorporation\b", r"\btechnologies\b",
            r"\btech\b", r"\bsolutions\b", r"\bsystems\b", r"\bgroup\b"
        ]
        for s in suffixes:
            name = re.sub(s, "", name, flags=re.IGNORECASE)
        # Remove punctuation and extra whitespace
        name = re.sub(r"[^\w\s]", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name

    @staticmethod
    def normalize_title(title: str) -> str:
        """Normalize job title for fuzzy matching."""
        if not title:
            return ""
        t = title.lower().strip()
        t = re.sub(r"[^\w\s]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    # Query parameters that only track campaigns/referrers and never identify a job
    TRACKING_PARAMS = {
        "ref", "referrer", "source", "src", "utm_source", "utm_medium", "utm_campaign",
        "utm_term", "utm_content", "gclid", "fbclid", "mc_cid", "mc_eid", "trk", "trackingid",
    }

    @classmethod
    def normalize_url(cls, url: str) -> str:
        """
        Normalise a job URL for comparison: lowercase scheme/host, drop fragment, trailing slash
        and tracking parameters. Identifying query parameters (e.g. ?id=123, ?gh_jid=...) are kept,
        because many ATS pages differ only by query string.
        """
        if not url:
            return ""
        try:
            parsed = urllib.parse.urlparse(url.strip())
            query = [
                (k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
                if k.lower() not in cls.TRACKING_PARAMS and not k.lower().startswith("utm_")
            ]
            query.sort()
            clean = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
            if query:
                clean += "?" + urllib.parse.urlencode(query)
            return clean
        except Exception:
            return url.strip().rstrip("/").lower()

    @classmethod
    async def check_duplicate(
        cls,
        db: AsyncSession,
        url: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        external_id: Optional[str] = None,
        source: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if an opportunity already exists in the database.
        Order: (source, external_id) -> normalised URL -> normalised company + title (+ location when both known).
        Returns: (is_duplicate, reason)
        """
        # 1. External ID, scoped to the same source (IDs are only unique within one source)
        if external_id and source:
            ext_res = await db.execute(
                select(Job.company).where(Job.job_id_external == external_id, Job.source == source).limit(1)
            )
            match_company = ext_res.scalars().first()
            if match_company is not None:
                return True, f"Same {source} job ID '{external_id}' already stored (Company: {match_company})"

        # 2. Normalised URL
        if url:
            norm_url = cls.normalize_url(url)
            rows = await db.execute(select(Job.url, Job.title, Job.company).where(Job.url.isnot(None)))
            for j_url, j_title, j_company in rows.all():
                if cls.normalize_url(j_url) == norm_url:
                    return True, f"Same URL as '{j_title}' at {j_company}"

        # 3. Company + title (+ location when both sides have one)
        if company and title:
            norm_comp = cls.normalize_company(company)
            norm_tit = cls.normalize_title(title)
            norm_loc = cls.normalize_title(location or "")
            if norm_comp and norm_tit:
                rows = await db.execute(select(Job.company, Job.title, Job.location, Job.status))
                for j_company, j_title, j_location, j_status in rows.all():
                    if not j_company or not j_title:
                        continue
                    if cls.normalize_company(j_company) != norm_comp or cls.normalize_title(j_title) != norm_tit:
                        continue
                    db_loc = cls.normalize_title(j_location or "")
                    if norm_loc and db_loc and norm_loc != db_loc:
                        continue  # same role title in a different city is a different opening
                    return True, f"'{j_title}' at '{j_company}' already in database (Status: {j_status})"

        return False, None
