"""
Stage 9 tests: phone access token (remote detection, pairing, modes, rotation, DNS rebinding),
security headers, PII redaction (logs and stored browser logs), log file, SQLite pragmas,
backup / verify / restore.
"""

import json
import logging
import os
import sqlite3
import uuid
import zipfile

import pytest
from sqlalchemy import text

from backend.config import get_settings
from backend.database.db import AsyncSessionLocal, engine
from backend.database.models import Application, Job
from backend.logging_setup import redact
from backend.maintenance import backup
from backend.services import lan_access

pytestmark = pytest.mark.asyncio

PHONE = {"x-forwarded-for": "192.168.1.50"}           # what the Vite proxy adds for an iPhone


@pytest.fixture(autouse=True)
def fresh_lan_config():
    path = os.path.join(get_settings().STORAGE_DIR, "lan_access.json")
    if os.path.exists(path):
        os.remove(path)
    lan_access.reset_cache()
    yield
    lan_access.reset_cache()


# --------------------------------------------------------------------------- classification
@pytest.mark.parametrize("client,headers,local", [
    ("127.0.0.1", {"host": "127.0.0.1:8000"}, True),
    ("::1", {"host": "localhost:8000"}, True),
    ("127.0.0.1", {"host": "localhost:5173", "x-forwarded-for": "127.0.0.1"}, True),
    ("127.0.0.1", {"host": "127.0.0.1:8000", "x-forwarded-for": "::ffff:127.0.0.1"}, True),
    ("127.0.0.1", {"host": "127.0.0.1:8000", "x-forwarded-for": "192.168.1.50"}, False),          # phone via proxy
    ("127.0.0.1", {"host": "127.0.0.1:8000", "x-forwarded-for": "127.0.0.1, 192.168.1.50"}, False),  # spoof attempt
    ("127.0.0.1", {"host": "127.0.0.1:8000", "x-forwarded-for": "not-an-ip"}, False),
    ("192.168.1.50", {"host": "192.168.1.10:8000"}, False),                                        # bound to LAN
    ("127.0.0.1", {"host": "evil.example:8000"}, False),                                           # DNS rebinding
    ("127.0.0.1", {"host": "[::1]:8000"}, True),
])
async def test_local_request_detection(client, headers, local):
    assert lan_access.is_local_request(client, headers) is local


# --------------------------------------------------------------------------- gate
async def test_local_needs_no_token(client):
    assert (await client.get("/api/profile")).status_code == 200


async def test_phone_without_token_is_refused(client):
    r = await client.get("/api/profile", headers=PHONE)
    assert r.status_code == 401 and r.json()["code"] == "lan_token_required"
    r = await client.post("/api/scheduler/trigger", headers=PHONE)
    assert r.status_code == 401
    assert (await client.get("/docs", headers=PHONE)).status_code == 401
    assert (await client.get("/api/profile", headers={**PHONE, "x-kitkat-token": "wrong" * 6})).status_code == 401


async def test_dns_rebinding_host_is_refused(client):
    r = await client.get("/api/profile", headers={"host": "attacker.example"})
    assert r.status_code == 401


async def test_pairing_sets_httponly_cookie_and_unlocks(client):
    token = lan_access.load()["token"]
    w = (await client.get("/api/security/whoami", headers=PHONE)).json()
    assert w == {"local": False, "authorized": False, "mode": "token"}
    bad = await client.post("/api/security/pair", json={"token": "x" * 32}, headers=PHONE)
    assert bad.status_code == 401
    r = await client.post("/api/security/pair", json={"token": token}, headers=PHONE)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "kk_token=" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert (await client.get("/api/profile", headers=PHONE)).status_code == 200            # cookie
    client.cookies.clear()
    assert (await client.get("/api/profile", headers={**PHONE, "x-kitkat-token": token})).status_code == 200


async def test_pairing_secure_cookie_over_https(client):
    token = lan_access.load()["token"]
    r = await client.post("/api/security/pair", json={"token": token}, headers={**PHONE, "x-forwarded-proto": "https"})
    assert "secure" in r.headers["set-cookie"].lower()
    client.cookies.clear()


async def test_token_admin_is_local_only(client):
    token = lan_access.load()["token"]
    auth = {**PHONE, "x-kitkat-token": token}
    assert (await client.get("/api/security/lan-access", headers=auth)).status_code == 403
    assert (await client.post("/api/security/lan-access/rotate", headers=auth)).status_code == 403
    assert (await client.post("/api/security/lan-access/mode", json={"mode": "off"}, headers=auth)).status_code == 403
    assert (await client.get("/api/maintenance/backups", headers=auth)).status_code == 403
    a = (await client.get("/api/security/lan-access", params={"base_url": "http://192.168.1.10:5173"})).json()
    assert a["token"] == token and a["pair_url"] == f"http://192.168.1.10:5173/#pair={token}"
    assert "pair_url" not in (await client.get("/api/security/lan-access", params={"base_url": "javascript:x"})).json()


async def test_rotation_invalidates_old_token(client):
    old = lan_access.load()["token"]
    new = (await client.post("/api/security/lan-access/rotate")).json()["token"]
    assert new != old and len(new) >= 30
    assert (await client.get("/api/profile", headers={**PHONE, "x-kitkat-token": old})).status_code == 401
    assert (await client.get("/api/profile", headers={**PHONE, "x-kitkat-token": new})).status_code == 200
    lan_access.reset_cache()                                                   # survives a restart
    assert lan_access.load()["token"] == new


async def test_mode_off_refuses_even_with_token(client):
    token = lan_access.load()["token"]
    assert (await client.post("/api/security/lan-access/mode", json={"mode": "off"})).json() == {"mode": "off"}
    r = await client.get("/api/profile", headers={**PHONE, "x-kitkat-token": token})
    assert r.status_code == 403 and r.json()["code"] == "lan_access_off"
    assert (await client.post("/api/security/pair", json={"token": token}, headers=PHONE)).status_code == 403
    assert (await client.get("/api/profile")).status_code == 200              # this computer still works
    assert (await client.post("/api/security/lan-access/mode", json={"mode": "open"})).status_code == 422


async def test_app_shell_loads_before_pairing(client):
    if not os.path.exists(os.path.join(__import__("backend.main").main.frontend_dist_dir, "index.html")):
        pytest.skip("frontend not built")
    assert (await client.get("/ui/", headers=PHONE)).status_code == 200
    assert (await client.get("/ui/manifest.json", headers=PHONE)).status_code == 200


async def test_token_file_is_private_and_not_in_repo():
    cfg = lan_access.load()
    path = os.path.join(get_settings().STORAGE_DIR, "lan_access.json")
    assert json.load(open(path))["token"] == cfg["token"]
    if os.name == "posix":
        assert oct(os.stat(path).st_mode & 0o777) == "0o600"
    gi = open(os.path.join(os.path.dirname(__file__), "..", ".gitignore")).read()
    assert "storage/lan_access.json" in gi and "storage/backups/" in gi


# --------------------------------------------------------------------------- headers
async def test_security_headers(client):
    r = await client.get("/api/profile")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    if os.path.exists(os.path.join(__import__("backend.main").main.frontend_dist_dir, "index.html")):
        csp = (await client.get("/ui/")).headers["content-security-policy"]
        assert "frame-ancestors 'none'" in csp and "script-src 'self'" in csp


# --------------------------------------------------------------------------- redaction & logs
def test_redact_masks_pii_but_not_dates_or_ids():
    s = redact("Mail test.candidate@example.com, call +91 98765 43210 or 9876543210; token=abcDEF123456789xyz")
    assert "example.com" not in s and "98765" not in s and "9876543210" not in s and "abcDEF" not in s
    assert s.count("[email hidden]") == 1 and s.count("[phone hidden]") == 2
    kept = ("Run 2026-11-26 09:00 IST, draft 3f2a9c1e-77b0-4c1d-9e0f-1234abcd5678, score 86.5, 12 jobs, "
            "saved kitkat-backup-20261126-053313-auto.zip")
    assert redact(kept) == kept
    tok = lan_access.load()["token"]
    assert tok not in redact(f"bad header {tok}")


def test_log_records_are_redacted_and_written_as_json():
    from backend.logging_setup import LOG_FILE_NAME
    lg = logging.getLogger("agent_kitkat.test_stage9")
    lg.warning("Contact %s at %s", "test.candidate@example.com", "+91-98765-43210")
    for h in logging.getLogger().handlers:
        h.flush()
    path = os.path.join(get_settings().LOGS_DIR, LOG_FILE_NAME)
    last = [json.loads(l) for l in open(path, encoding="utf-8") if "agent_kitkat.test_stage9" in l][-1]
    assert last["level"] == "WARNING" and "[email hidden]" in last["msg"] and "[phone hidden]" in last["msg"]
    assert "98765" not in open(path, encoding="utf-8").read()


async def test_old_browser_logs_are_scrubbed_on_startup():
    from backend.database.db import _scrub_stored_browser_logs
    jid, aid = str(uuid.uuid4()), str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(Job(id=jid, title="t", company="c", url=f"https://x/{jid}", raw_text="x"))
        s.add(Application(id=aid, job_id=jid, status="draft", stage="prepared", browser_logs=[
            "[10:00:01] Filled field 'phone' -> +91-0000000000",
            "[10:00:02] Filled field 'email' -> test.candidate@example.com",
            "[10:00:03] Page loaded: https://boards.greenhouse.io/acme/jobs/123",
        ]))
        await s.commit()
    await _scrub_stored_browser_logs()
    await _scrub_stored_browser_logs()        # idempotent
    async with AsyncSessionLocal() as s:
        logs = (await s.get(Application, aid)).browser_logs
    assert logs[0].endswith("'phone' -> [value hidden]") and logs[1].endswith("'email' -> [value hidden]")
    assert logs[2] == "[10:00:03] Page loaded: https://boards.greenhouse.io/acme/jobs/123"


async def test_sqlite_pragmas():
    async with engine.connect() as conn:
        assert (await conn.execute(text("PRAGMA busy_timeout"))).scalar() == 5000
        assert (await conn.execute(text("PRAGMA journal_mode"))).scalar().lower() == "wal"


# --------------------------------------------------------------------------- backups
async def _seed_data():
    s = get_settings()
    os.makedirs(s.RESUMES_DIR, exist_ok=True)
    with open(os.path.join(s.RESUMES_DIR, "cv.pdf"), "wb") as f:
        f.write(b"%PDF-1.4 test resume")
    jid = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(Job(id=jid, title="Backup Intern", company="Acme", url=f"https://x/{jid}", raw_text="x"))
        await db.commit()
    return jid


async def test_backup_create_verify_and_restore(tmp_path):
    s = get_settings()
    jid = await _seed_data()
    m = backup.create("manual", dest_dir=str(tmp_path))
    assert m["counts"]["jobs"] >= 1 and "resumes/cv.pdf" in m["files"] and "database.sqlite" in m["files"]
    assert backup.verify(m["path"])["label"] == "manual"

    # change the live data, then restore
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM jobs"))
        await db.commit()
    os.remove(os.path.join(s.RESUMES_DIR, "cv.pdf"))
    open(os.path.join(s.RESUMES_DIR, "new.pdf"), "wb").write(b"new")
    await engine.dispose()                       # release the DB file like a stopped app would
    out = backup.restore(m["path"], force=True)  # the test server isn't on the real port
    assert out["safety_backup"] and os.path.exists(os.path.join(backup.backups_dir(), out["safety_backup"]))
    assert os.path.exists(os.path.join(s.RESUMES_DIR, "cv.pdf")) and not os.path.exists(os.path.join(s.RESUMES_DIR, "new.pdf"))
    con = sqlite3.connect(s.database_path)
    assert con.execute("SELECT COUNT(*) FROM jobs WHERE id=?", (jid,)).fetchone()[0] == 1
    con.close()


def _tamper(src, dst, edit):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            name, data = edit(item.filename, data)
            if name:
                zout.writestr(name, data)


async def test_verify_rejects_damaged_or_unsafe_backups(tmp_path):
    await _seed_data()
    good = backup.create("manual", dest_dir=str(tmp_path))["path"]
    bad1 = str(tmp_path / "b1.zip")
    _tamper(good, bad1, lambda n, d: (n, d + b"x") if n == "resumes/cv.pdf" else (n, d))
    with pytest.raises(backup.BackupError, match="Checksum"):
        backup.verify(bad1)
    bad2 = str(tmp_path / "b2.zip")
    _tamper(good, bad2, lambda n, d: (n, d))
    with zipfile.ZipFile(bad2, "a") as z:
        z.writestr("../evil.txt", "x")
    with pytest.raises(backup.BackupError, match="Unsafe"):
        backup.verify(bad2)
    bad3 = str(tmp_path / "b3.zip")
    _tamper(good, bad3, lambda n, d: (None, d) if n == "manifest.json" else (n, d))
    with pytest.raises(backup.BackupError, match="manifest"):
        backup.verify(bad3)
    with pytest.raises(backup.BackupError):
        backup.verify(__file__)


async def test_restore_refuses_while_running(tmp_path, monkeypatch):
    await _seed_data()
    good = backup.create("manual", dest_dir=str(tmp_path))["path"]
    monkeypatch.setattr(backup, "backend_running", lambda port=None: True)
    with pytest.raises(backup.BackupError, match="Stop it first"):
        backup.restore(good)


async def test_auto_backup_once_a_day_and_pruning(monkeypatch):
    await _seed_data()
    for f in os.listdir(backup.backups_dir()):
        os.remove(os.path.join(backup.backups_dir(), f))
    assert backup.auto_backup_if_due() is not None
    assert backup.auto_backup_if_due() is None                 # already one today
    for _ in range(9):
        backup.create("auto")
    backup.create("manual")
    backup.prune("auto", keep=7)
    labels = [b["label"] for b in backup.list_backups()]
    assert labels.count("auto") == 7 and labels.count("manual") == 1


async def test_backup_api_local(client):
    await _seed_data()
    r = await client.post("/api/maintenance/backups")
    assert r.status_code == 200 and r.json()["files"] >= 2
    name = r.json()["name"]
    lst = (await client.get("/api/maintenance/backups")).json()
    assert any(b["name"] == name for b in lst["items"])
    dl = await client.get(f"/api/maintenance/backups/{name}")
    assert dl.status_code == 200 and dl.content[:2] == b"PK"
    assert (await client.get("/api/maintenance/backups/..%2Fsecret.zip")).status_code in (400, 404)


def test_cli_create_and_verify(capsys):
    assert backup.main(["create", "--label", "cli"]) == 0
    name = [b["name"] for b in backup.list_backups() if b.get("label") == "cli"][0]
    assert backup.main(["verify", name]) == 0
    assert "checksums match" in capsys.readouterr().out
    assert backup.main(["verify", "does-not-exist.zip"]) == 2
