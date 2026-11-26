"""
LAN access control.

Agent KitKat is meant for one person. On this computer (localhost) everything works as before.
Requests from any other device on the Wi-Fi (your iPhone, reaching the API through the
frontend server started by start.bat) must carry the access token. The token is created
on first start, kept in storage/lan_access.json (git-ignored storage, never in code),
and handed to the phone by scanning a QR code in Settings.

Modes (Settings → Phone access):
  * "token" (default): other devices need the token.
  * "off": other devices are refused even with the token.

How "another device" is detected (any one is enough):
  * the TCP peer is not a loopback address (backend bound to the LAN directly), or
  * X-Forwarded-For contains a non-loopback address (the Vite proxy adds the phone's
    address; a client can prepend fake entries but cannot remove the proxy's), or
  * the Host header is not a local name. This also blocks DNS-rebinding attacks, where a
    website points its own domain at 127.0.0.1 to reach this API from your browser.
"""

import ipaddress
import json
import logging
import os
import secrets
import threading
from datetime import datetime
from typing import Dict, Optional

from backend.config import get_settings

logger = logging.getLogger("agent_kitkat.lan_access")

TOKEN_HEADER = "x-kitkat-token"
TOKEN_COOKIE = "kk_token"
MODES = ("token", "off")

_lock = threading.Lock()
_cache: Optional[Dict[str, str]] = None


def _path() -> str:
    return os.path.join(get_settings().STORAGE_DIR, "lan_access.json")


def _write(data: Dict[str, str]) -> None:
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass  # Windows: file ACLs are inherited from the user's folder
    os.replace(tmp, path)


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def load() -> Dict[str, str]:
    """Current config; creates it (with a fresh token) on first use."""
    global _cache
    with _lock:
        if _cache is not None:
            return dict(_cache)
        data: Dict[str, str] = {}
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            logger.error("Could not read %s (%s); creating a new access token.", _path(), e)
        changed = False
        if not isinstance(data.get("token"), str) or len(data["token"]) < 20:
            data["token"] = _new_token()
            data["created_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            changed = True
        if data.get("mode") not in MODES:
            data["mode"] = "token"
            changed = True
        if changed:
            _write(data)
            logger.info("Created a phone access token in %s", _path())
        _cache = data
        return dict(data)


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def rotate_token() -> Dict[str, str]:
    data = load()
    data["token"] = _new_token()
    data["created_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _lock:
        _write(data)
        global _cache
        _cache = data
    logger.warning("Phone access token rotated; paired devices must scan the new QR code.")
    return dict(data)


def set_mode(mode: str) -> Dict[str, str]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    data = load()
    data["mode"] = mode
    with _lock:
        _write(data)
        global _cache
        _cache = data
    logger.warning("Phone access mode set to %s", mode)
    return dict(data)


def token_matches(candidate: Optional[str]) -> bool:
    if not candidate:
        return False
    return secrets.compare_digest(candidate.encode(), load()["token"].encode())


# ------------------------------------------------------------------ request classification
def _is_loopback_ip(value: str) -> bool:
    value = (value or "").strip().strip("[]")
    if not value:
        return True
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False  # garbage in a forwarded header: treat as remote
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_loopback


def local_hostnames() -> set:
    extra = os.getenv("LOCAL_HOSTNAMES", "")
    return {"localhost", "127.0.0.1", "::1"} | {h.strip().lower() for h in extra.split(",") if h.strip()}


def _host_name(host_header: str) -> str:
    host = (host_header or "").strip().lower()
    if host.startswith("["):                      # [::1]:8000
        return host[1:host.find("]")] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def is_local_request(client_host: Optional[str], headers) -> bool:
    """True only for requests that come from this computer itself."""
    if client_host and not _is_loopback_ip(client_host):
        return False
    xff = headers.get("x-forwarded-for")
    if xff and not all(_is_loopback_ip(part) for part in xff.split(",")):
        return False
    if _host_name(headers.get("host", "")) not in local_hostnames():
        return False
    return True


def presented_token(headers, cookies) -> Optional[str]:
    return headers.get(TOKEN_HEADER) or cookies.get(TOKEN_COOKIE)
