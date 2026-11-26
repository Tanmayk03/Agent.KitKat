"""
Logging for Agent KitKat.

* Console: the usual one-line format.
* File: storage/logs/agent_kitkat.log as JSON lines (one object per line: ts, level, logger,
  msg, and exc if any), rotated at 5 MB with 5 old files kept (about 30 MB at most).
* Every handler masks personal data before it is written: e-mail addresses, phone numbers,
  the phone access token, and "token=" / "Bearer" values. The same `redact()` is used for
  the browser-automation log that is stored with each application.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Iterable

LOG_FILE_NAME = "agent_kitkat.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5

_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63})+")
_PHONE = re.compile(r"(?<![\w+])\+?\d[\d ()\-.]{8,18}\d(?!\w)")
_DATE_LIKE = re.compile(r"^(?:\d{4}-\d{2}-\d{2}|\d{8}[-_T ]?\d{4,6}$)")   # dates and 20261126-053313 stamps
_TOKENISH = re.compile(r"(?i)\b(token|access[_-]?code|pair|password|secret|api[_-]?key)(\s*[=:]\s*)([^\s&#\"',;]+)")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")


def _phone_sub(m: "re.Match") -> str:
    text = m.group(0)
    digits = sum(ch.isdigit() for ch in text)
    if digits < 10 or digits > 15 or _DATE_LIKE.match(text):
        return text
    return "[phone hidden]"


def _secret_values() -> Iterable[str]:
    try:
        from backend.services import lan_access
        data = lan_access._cache or {}
        tok = data.get("token")
        return [tok] if tok else []
    except Exception:  # logging must never fail because of this
        return []


def redact(text: str) -> str:
    """Mask e-mails, phone numbers and secrets in free text."""
    if not text:
        return text
    out = str(text)
    for secret in _secret_values():
        out = out.replace(secret, "[token hidden]")
    out = _EMAIL.sub("[email hidden]", out)
    out = _BEARER.sub("Bearer [hidden]", out)
    out = _TOKENISH.sub(lambda m: f"{m.group(1)}{m.group(2)}[hidden]", out)
    out = _PHONE.sub(_phone_sub, out)
    return out


class RedactingFilter(logging.Filter):
    """Formats the message once, masks it, and freezes it on the record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        clean = redact(msg)
        if clean != msg or record.args:
            record.msg, record.args = clean, None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(data, ensure_ascii=False)


_configured_for = None


def setup_logging(logs_dir: str, level: int = logging.INFO) -> str:
    """Configure root + uvicorn loggers. Safe to call more than once. Returns the log file path."""
    global _configured_for
    path = os.path.join(logs_dir, LOG_FILE_NAME)
    if _configured_for == path:
        return path
    os.makedirs(logs_dir, exist_ok=True)

    redactor = RedactingFilter()
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    console.addFilter(redactor)
    file_handler = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    file_handler.addFilter(redactor)

    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_kitkat", False):
            root.removeHandler(h)
            h.close()
    for h in (console, file_handler):
        h._kitkat = True
        root.addHandler(h)
    root.setLevel(level)

    # uvicorn's loggers don't propagate to root; give them the file handler and the filter.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        for h in list(lg.handlers):
            if getattr(h, "_kitkat", False):
                lg.removeHandler(h)
            elif not any(isinstance(f, RedactingFilter) for f in h.filters):
                h.addFilter(redactor)
        if not lg.propagate:
            lg.addHandler(file_handler)
    _configured_for = path
    return path
