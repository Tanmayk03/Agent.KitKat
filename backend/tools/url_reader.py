"""
Agent KitKat - URL Reader Tool
Retrieves public job postings via HTTP, strips boilerplate HTML,
and safely extracts readable job descriptions.

Strict Rule: Never bypass CAPTCHA, anti-bot gates, or login walls.
If access is restricted or content is JavaScript-rendered behind a wall,
flag requires_manual_paste=True and notify the user to paste the raw text.
"""

import re
import logging
from typing import Tuple, Optional
import httpx
from bs4 import BeautifulSoup

from backend.config import get_settings
from backend.security import is_public_http_url

settings = get_settings()
MAX_REDIRECTS = 5

logger = logging.getLogger("agent_kitkat.url_reader")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1"
}


class URLReader:
    """Tool to fetch and extract textual content from public web pages."""

    @staticmethod
    async def fetch_job_page(url: str, timeout: float = 15.0) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Fetches web page content at url.
        Returns:
            (extracted_clean_text, error_message, requires_manual_paste)
        """
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        blocked_msg = (
            "This URL points to this computer or your local network, which Agent KitKat will not fetch. "
            "Please paste the job description text instead."
        )
        try:
            async with httpx.AsyncClient(
                headers=BROWSER_HEADERS,
                timeout=timeout,
                follow_redirects=False,
                trust_env=settings.HTTP_TRUST_ENV
            ) as client:
                # Follow redirects manually so every hop is checked against the SSRF guard
                current = url
                for _ in range(MAX_REDIRECTS + 1):
                    if not is_public_http_url(current):
                        return (None, blocked_msg, True)
                    response = await client.get(current)
                    if response.is_redirect and response.headers.get("location"):
                        current = str(response.url.join(response.headers["location"]))
                        continue
                    break
                else:
                    return (None, "Too many redirects. Please paste the job description text.", True)

                if response.status_code == 403 or response.status_code == 401:
                    logger.warning("Access restricted (HTTP %d) for URL: %s", response.status_code, url)
                    return (
                        None,
                        f"Website returned HTTP {response.status_code} (Access Restricted / Login Required). "
                        "Please copy and paste the job description text manually in Mode B.",
                        True
                    )

                if response.status_code != 200:
                    return (
                        None,
                        f"Failed to fetch job page (HTTP status {response.status_code}). "
                        "Please paste the job description text manually.",
                        True
                    )

                html_content = response.text

                # Check for common bot challenge / captcha pages in response text
                lower_html = html_content.lower()
                bot_markers = [
                    "cf-challenge", "cloudflare ray id", "captcha", "security check",
                    "please verify you are human", "enable javascript to continue",
                    "authwall", "sign in to view"
                ]
                if any(marker in lower_html for marker in bot_markers) and len(html_content) < 5000:
                    return (
                        None,
                        "The destination page is protected by a verification challenge or login screen. "
                        "Please copy and paste the job description text manually.",
                        True
                    )

                clean_text = URLReader.clean_html(html_content)

                if len(clean_text) < 100:
                    return (
                        None,
                        "Could not extract sufficient text from this URL (it may require JavaScript to render). "
                        "Please paste the job description text directly.",
                        True
                    )

                return (clean_text, None, False)

        except httpx.ConnectError:
            return (
                None,
                f"Could not connect to server at {url}. Please verify the URL or paste the job description text.",
                True
            )
        except httpx.TimeoutException:
            return (
                None,
                f"Connection to {url} timed out after {timeout} seconds. Please paste the job description text manually.",
                True
            )
        except Exception as e:
            logger.exception("Unexpected error fetching URL %s: %s", url, str(e))
            return (
                None,
                f"Error retrieving job posting: {str(e)}. Please paste the job description text.",
                True
            )

    @staticmethod
    def clean_html(html: str) -> str:
        """Parse HTML, discard useless elements, and return clean readable text."""
        soup = BeautifulSoup(html, "html.parser")

        # Discard script, style, nav, footer, header, svg, etc.
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "svg"]):
            tag.decompose()

        # Get text with clean spacing
        text = soup.get_text(separator="\n")

        # Clean excessive newlines and whitespace
        lines = [line.strip() for line in text.splitlines()]
        cleaned_lines = [line for line in lines if line]
        result = "\n".join(cleaned_lines)
        return re.sub(r"\n{3,}", "\n\n", result).strip()
