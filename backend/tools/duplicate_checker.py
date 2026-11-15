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

    @staticmethod
    def normalize_url(url: str) -> str:
        """Strip tracking parameters, query strings, and trailing slashes from URLs."""
        if not url:
            return ""
        try:
            parsed = urllib.parse.urlparse(url.strip())
            # Reconstruct URL without query string or fragment
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            return clean.lower()
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
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if an opportunity already exists in the database.
        Returns: (is_duplicate: bool, reason: Optional[str])
        """
        # 1. External ID check (if provided by API source)
        if external_id:
            ext_stmt = select(Job).where(Job.job_id_external == external_id)
            ext_res = await db.execute(ext_stmt)
            match = ext_res.scalar_one_or_none()
            if match:
                return True, f"Duplicate external job ID '{external_id}' (Company: {match.company})"

        # 2. Clean URL match check
        if url:
            norm_url = cls.normalize_url(url)
            # Check all jobs with URLs
            url_stmt = select(Job).where(Job.url.isnot(None))
            url_res = await db.execute(url_stmt)
            all_jobs = url_res.scalars().all()
            for j in all_jobs:
                if j.url and cls.normalize_url(j.url) == norm_url:
                    return True, f"Duplicate application URL matches job '{j.title}' at {j.company}"

        # 3. Company & Role Title Match Check
        if company and title:
            norm_comp = cls.normalize_company(company)
            norm_tit = cls.normalize_title(title)

            if norm_comp and norm_tit:
                # Query jobs with similar company
                comp_stmt = select(Job)
                res = await db.execute(comp_stmt)
                jobs = res.scalars().all()

                for j in jobs:
                    if j.company and j.title:
                        db_comp = cls.normalize_company(j.company)
                        db_tit = cls.normalize_title(j.title)
                        # Match if company names match and titles match
                        if db_comp and db_comp == norm_comp and db_tit == norm_tit:
                            return True, f"Duplicate listing: '{j.title}' at '{j.company}' already in database (Status: {j.status})"

        return False, None
