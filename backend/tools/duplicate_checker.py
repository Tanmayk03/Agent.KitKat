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
    def dedupe_key(cls, company: Optional[str], title: Optional[str], location: Optional[str]) -> Optional[str]:
        comp, tit = cls.normalize_company(company or ""), cls.normalize_title(title or "")
        if not comp or not tit:
            return None
        return f"{comp}|{tit}|{cls.normalize_title(location or '')}"

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
        Check if an opportunity already exists in the database (all lookups use indexed columns).
        Order: (source, external_id) -> normalised URL -> normalised company + title (+ location when both known).
        Returns: (is_duplicate, reason)
        """
        match = await cls.find_existing(db, url, company, title, external_id, source, location)
        if match is None:
            return False, None
        job, reason = match
        return True, reason

    @classmethod
    async def find_existing(
        cls,
        db: AsyncSession,
        url: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        external_id: Optional[str] = None,
        source: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Optional[Tuple[Job, str]]:
        # 1. External ID, scoped to the same source (IDs are only unique within one source)
        if external_id and source:
            job = (await db.execute(
                select(Job).where(Job.job_id_external == external_id, Job.source == source).limit(1)
            )).scalars().first()
            if job is not None:
                return job, f"Same {source} job ID '{external_id}' already stored (Company: {job.company})"

        # 2. Normalised URL
        if url:
            job = (await db.execute(
                select(Job).where(Job.url_key == cls.normalize_url(url)).limit(1)
            )).scalars().first()
            if job is not None:
                return job, f"Same URL as '{job.title}' at {job.company}"

        # 3. Company + title (+ location when both sides have one)
        key = cls.dedupe_key(company, title, location)
        if key:
            prefix = key.rsplit("|", 1)[0] + "|"
            norm_loc = key.rsplit("|", 1)[1]
            rows = (await db.execute(
                select(Job).where(Job.dedupe_key >= prefix, Job.dedupe_key < prefix + "\uffff")
            )).scalars().all()
            for job in rows:
                db_loc = (job.dedupe_key or "").rsplit("|", 1)[-1]
                if norm_loc and db_loc and norm_loc != db_loc:
                    continue  # same role title in a different city is a different opening
                return job, f"'{job.title}' at '{job.company}' already in database (Status: {job.status})"
        return None


# Keep dedupe_key / url_key in sync on every insert/update of a Job, wherever it is created.
from sqlalchemy import event  # noqa: E402


@event.listens_for(Job, "before_insert")
@event.listens_for(Job, "before_update")
def _sync_job_keys(mapper, connection, target: Job) -> None:
    target.dedupe_key = DuplicateChecker.dedupe_key(target.company, target.title, target.location)
    target.url_key = DuplicateChecker.normalize_url(target.url) if target.url else None
