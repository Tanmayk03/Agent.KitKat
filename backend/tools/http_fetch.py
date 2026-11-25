"""
Agent KitKat - Resilient HTTP fetching for job sources.

- Per-request timeout (set on the client)
- Up to `retries` retries with exponential backoff + jitter for network errors, HTTP 429 and 5xx
- Honours `Retry-After` (seconds or HTTP date), capped so one source cannot stall a run
- Never retries 4xx other than 429 (those will not fix themselves)
- Raises SourceFetchError with a human-readable reason when it gives up
"""

import asyncio
import logging
import random
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from backend.config import get_settings

logger = logging.getLogger("agent_kitkat.http_fetch")
settings = get_settings()

MAX_RETRY_AFTER_SECONDS = 30.0
USER_AGENT = "AgentKitKat/0.3 (personal job-search assistant; respects robots and rate limits)"

# Indirection so tests can skip real sleeping
sleep = asyncio.sleep


class SourceFetchError(RuntimeError):
    """A discovery source could not be fetched (network error, HTTP error, bad payload)."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def make_client(timeout: float = 20.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout,
        trust_env=settings.HTTP_TRUST_ENV,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/rss+xml, */*"},
    )


def _retry_after_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


async def fetch(
    client: httpx.AsyncClient,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    retries: int = 3,
    backoff_base: float = 1.0,
) -> httpx.Response:
    """GET with retries. Returns a 200 response or raises SourceFetchError."""
    last_error = "unknown error"
    last_status: Optional[int] = None
    for attempt in range(retries + 1):
        wait: Optional[float] = None
        try:
            res = await client.get(url, params=params)
        except httpx.HTTPError as e:
            last_error = f"{type(e).__name__}: {e}"
            last_status = None
        else:
            if res.status_code == 200:
                return res
            last_status = res.status_code
            last_error = f"HTTP {res.status_code} from {url}"
            if res.status_code == 429:
                wait = _retry_after_seconds(res.headers.get("Retry-After"))
                last_error = f"Rate limited (HTTP 429) by {url}"
            elif res.status_code < 500:
                raise SourceFetchError(last_error, res.status_code)  # not retryable
        if attempt == retries:
            break
        if wait is None:
            wait = backoff_base * (2 ** attempt) + random.uniform(0, backoff_base / 2)
        wait = min(wait, MAX_RETRY_AFTER_SECONDS)
        logger.info("Retrying %s in %.1fs (attempt %d/%d): %s", url, wait, attempt + 1, retries, last_error)
        await sleep(wait)
    raise SourceFetchError(f"{last_error} (after {retries + 1} attempts)", last_status)
