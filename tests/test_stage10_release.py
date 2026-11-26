"""
Stage 10 release checks: nothing private or secret is tracked in Git, the install/start/test
scripts exist and stay safe, and the version is consistent everywhere it is shown.
"""

import json
import os
import re
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [f for f in out.splitlines() if f]
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")


def text_files():
    for f in tracked_files():
        if f.endswith(("package-lock.json", ".png", ".svg", ".ico", ".woff", ".woff2", ".pdf", ".docx")):
            continue
        path = os.path.join(ROOT, f)
        if os.path.isfile(path):
            yield f, open(path, encoding="utf-8", errors="ignore").read()


def test_no_private_files_tracked():
    bad = re.compile(r"(^|/)(\.env|\.env\.local|profile_seed\.json|lan_access\.json)$|\.(db|sqlite3?|pem|key|p12)$|^storage/backups/")
    assert [f for f in tracked_files() if bad.search(f)] == []


def test_no_secrets_in_tracked_files():
    patterns = {
        "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "AWS key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "GitHub token": re.compile(r"\b(ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}"),
        "Slack token": re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}"),
        "generic api key assignment": re.compile(r"(?i)\b(api[_-]?key|secret|password)\s*[:=]\s*['\"][A-Za-z0-9/+_\-]{16,}['\"]"),
    }
    hits = [(f, name) for f, text in text_files() for name, rx in patterns.items() if rx.search(text)]
    assert hits == []


def test_only_placeholder_emails_in_tracked_files():
    email = re.compile(r"(?<![\w.@/-])[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b")
    allowed = ("example.com", "example.org", "example.net", "users.noreply.github.com")
    found = set()
    for f, text in text_files():
        for m in email.finditer(text):
            if not m.group(1).lower().endswith(allowed):
                found.add((f, m.group(0)))
    assert found == set()


def test_scripts_exist_and_never_delete_user_data():
    for name in ("install.ps1", "install.bat", "start.bat", "start_all.ps1", "stop.bat", "test.ps1",
                 "backup.bat", "restore.bat"):
        assert os.path.isfile(os.path.join(ROOT, name)), name
    for f, text in text_files():
        if f.startswith("scripts/") or f.endswith((".ps1", ".bat")):
            assert not re.search(r"(?i)\bDELETE\s+FROM\b|delete\((Application|ApplicationDraft|ApprovalRequest|Job)\)", text), f
            assert "Remove-Item" not in text or f == "install.ps1", f


def test_version_is_consistent():
    from backend.config import get_settings
    v = get_settings().APP_VERSION
    pkg = json.load(open(os.path.join(ROOT, "frontend", "package.json")))
    assert pkg["version"] == v
    changelog = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    assert f"## [{v}]" in changelog
