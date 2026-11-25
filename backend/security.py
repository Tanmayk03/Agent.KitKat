"""
Agent KitKat - Local security helpers.

Agent KitKat is a single-user app that runs on your laptop. The main threats are:
  * a random website you visit in the same browser calling http://127.0.0.1:8000
    (cross-site request forgery / data theft), and
  * other devices on the same Wi-Fi.

This module provides:
  * an origin allow-list (localhost + private LAN ranges + configured extras), used
    both for CORS and for rejecting cross-site state-changing requests, and
  * filename sanitisation for uploads, and
  * an SSRF guard for user-supplied URLs.
"""

import ipaddress
import os
import re
import socket
import uuid
from typing import Iterable, Optional
from urllib.parse import urlparse

LOCAL_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|\[::1\]"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r")(?::\d{1,5})?$"
)
_LOCAL_ORIGIN_RE = re.compile(LOCAL_ORIGIN_REGEX, re.IGNORECASE)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def is_allowed_origin(origin: Optional[str], extra_origins: Iterable[str] = ()) -> bool:
    """True if a browser Origin header belongs to this machine / private LAN / configured list."""
    if not origin:
        return True  # non-browser clients (curl, tests, scripts) send no Origin
    origin = origin.rstrip("/")
    if origin in set(extra_origins):
        return True
    return bool(_LOCAL_ORIGIN_RE.match(origin))


def safe_upload_name(file_name: str, allowed_exts: Iterable[str]) -> str:
    """
    Reduce an uploaded filename to a harmless basename.
    Strips any directory components (both / and \\), replaces unusual characters,
    and validates the extension. Raises ValueError for disallowed extensions.
    """
    base = re.split(r"[\\/]", file_name or "")[-1]
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext not in {e.lower() for e in allowed_exts}:
        raise ValueError(f"Unsupported file type '{ext or '(none)'}'.")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "file"
    return f"{stem[:80]}{ext}"


def unique_path_in(directory: str, file_name: str) -> str:
    """Join a sanitised name into directory and assert the result stays inside it."""
    path = os.path.abspath(os.path.join(directory, f"{uuid.uuid4()}_{file_name}"))
    root = os.path.abspath(directory)
    if os.path.commonpath([path, root]) != root:
        raise ValueError("Invalid upload path.")
    return path


def is_public_http_url(url: str) -> bool:
    """
    SSRF guard: only allow http(s) URLs whose host resolves exclusively to public addresses.
    Blocks localhost, private LAN, link-local, multicast and reserved ranges.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        # Unresolvable here: let the HTTP client report the connection error.
        return True
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            return False
    return True
