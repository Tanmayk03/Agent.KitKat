"""
Backup and restore for Agent KitKat.

A backup is one .zip in storage/backups/ containing:
  database.sqlite     a consistent copy made with SQLite's online-backup API (safe while running)
  resumes/            uploaded resumes
  applications/       prepared application files
  screenshots/        pre/post-submit screenshots
  profile_seed.json   if present
  manifest.json       app version, time, label, record counts, and a SHA-256 for every file

Not included: logs, older backups, and the phone access token (each install makes its own).

Command line (run from the project folder, with the venv active):
  python -m backend.maintenance.backup create [--label NAME]
  python -m backend.maintenance.backup list
  python -m backend.maintenance.backup verify <zip>
  python -m backend.maintenance.backup restore <zip> [--yes] [--force]

Restore refuses to run while Agent KitKat is running (stop it with stop.bat first), checks
the backup, and makes a "pre-restore" backup of the current data before replacing anything.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import socket
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.config import get_settings

logger = logging.getLogger("agent_kitkat.backup")

FORMAT = 1
DIRS = (("resumes", "RESUMES_DIR"), ("applications", "APPLICATIONS_DIR"), ("screenshots", "SCREENSHOTS_DIR"))
NAME_RE = re.compile(r"^kitkat-backup-\d{8}-\d{6}(?:-[a-z0-9-]{1,30})?\.zip$")
AUTO_KEEP = 7


class BackupError(Exception):
    pass


def backups_dir() -> str:
    d = os.path.join(get_settings().STORAGE_DIR, "backups")
    os.makedirs(d, exist_ok=True)
    return d


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _db_path() -> str:
    path = get_settings().database_path
    if not path:
        raise BackupError("Only the SQLite database can be backed up.")
    return path


def _copy_db(dest: str) -> None:
    path = _db_path()
    if not os.path.exists(path):
        raise BackupError(f"No database at {path} yet.")
    src = sqlite3.connect(path)  # a plain path (file: URIs differ on Windows); backup() only reads it
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _counts(db_file: str) -> Dict[str, Optional[int]]:
    out: Dict[str, Optional[int]] = {}
    con = sqlite3.connect(db_file)
    try:
        for table in ("jobs", "applications", "resumes", "application_drafts", "daily_reports"):
            try:
                out[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                out[table] = None
    finally:
        con.close()
    return out


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", (label or "manual").lower()).strip("-")[:30] or "manual"


def create(label: str = "manual", dest_dir: Optional[str] = None) -> Dict[str, Any]:
    """Make a backup zip and return its manifest (plus path and size)."""
    settings = get_settings()
    dest_dir = dest_dir or backups_dir()
    os.makedirs(dest_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"kitkat-backup-{stamp}-{_slug(label)}.zip"
    final = os.path.join(dest_dir, name)
    n = 1
    while os.path.exists(final):        # two backups in the same second
        n += 1
        name = f"kitkat-backup-{stamp}-{_slug(label)}-{n}.zip"
        final = os.path.join(dest_dir, name)

    with tempfile.TemporaryDirectory(prefix="kk_backup_") as tmp:
        db_copy = os.path.join(tmp, "database.sqlite")
        _copy_db(db_copy)
        entries: List[tuple] = [(db_copy, "database.sqlite")]
        for arc, key in DIRS:
            root = getattr(settings, key)
            if os.path.isdir(root):
                for dirpath, _dirs, files in os.walk(root):
                    for fn in sorted(files):
                        if fn == ".gitkeep":
                            continue
                        full = os.path.join(dirpath, fn)
                        rel = os.path.relpath(full, root).replace(os.sep, "/")
                        entries.append((full, f"{arc}/{rel}"))
        if os.path.isfile(settings.PROFILE_SEED_FILE):
            entries.append((settings.PROFILE_SEED_FILE, "profile_seed.json"))

        manifest = {
            "format": FORMAT,
            "app": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "label": _slug(label),
            "counts": _counts(db_copy),
            "files": {arc: {"sha256": _sha256(full), "size": os.path.getsize(full)} for full, arc in entries},
        }
        partial = final + ".partial"
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for full, arc in entries:
                z.write(full, arc)
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
        os.replace(partial, final)

    manifest.update(name=name, path=final, size=os.path.getsize(final))
    logger.info("Backup created: %s (%d files, %.1f MB)", name, len(entries), manifest["size"] / 1e6)
    return manifest


def _read_manifest(z: zipfile.ZipFile) -> Dict[str, Any]:
    try:
        m = json.loads(z.read("manifest.json"))
    except KeyError:
        raise BackupError("Not an Agent KitKat backup (manifest.json missing).")
    except ValueError:
        raise BackupError("manifest.json is damaged.")
    if m.get("format") != FORMAT or "files" not in m:
        raise BackupError(f"Unsupported backup format {m.get('format')!r}.")
    return m


def _safe_member(name: str) -> bool:
    if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name):
        return False
    parts = re.split(r"[\\/]", name)
    return ".." not in parts and name == name.strip()


def verify(path: str) -> Dict[str, Any]:
    """Check paths, every checksum and the database's integrity. Raises BackupError."""
    if not zipfile.is_zipfile(path):
        raise BackupError("Not a zip file.")
    with zipfile.ZipFile(path) as z:
        m = _read_manifest(z)
        names = set(z.namelist()) - {"manifest.json"}
        unsafe = [n for n in z.namelist() if not _safe_member(n)]
        if unsafe:
            raise BackupError(f"Unsafe path in backup: {unsafe[0]}")
        allowed_top = {"database.sqlite", "profile_seed.json"} | {arc for arc, _ in DIRS}
        stray = [n for n in names if n.split("/")[0] not in allowed_top]
        if stray:
            raise BackupError(f"Unexpected file in backup: {stray[0]}")
        if set(m["files"]) != names:
            raise BackupError("The file list does not match manifest.json.")
        if "database.sqlite" not in names:
            raise BackupError("database.sqlite missing.")
        for name, meta in m["files"].items():
            h = hashlib.sha256()
            with z.open(name) as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != meta["sha256"]:
                raise BackupError(f"Checksum mismatch: {name}")
        with tempfile.TemporaryDirectory(prefix="kk_verify_") as tmp:
            db = z.extract("database.sqlite", tmp)
            con = sqlite3.connect(db)
            try:
                result = con.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                con.close()
            if result != "ok":
                raise BackupError(f"Database integrity check failed: {result}")
    return m


def list_backups() -> List[Dict[str, Any]]:
    out = []
    for fn in sorted(os.listdir(backups_dir()), reverse=True):
        if not NAME_RE.match(fn):
            continue
        path = os.path.join(backups_dir(), fn)
        item: Dict[str, Any] = {"name": fn, "size": os.path.getsize(path)}
        try:
            with zipfile.ZipFile(path) as z:
                m = _read_manifest(z)
            item.update(created_at=m.get("created_at"), label=m.get("label"), counts=m.get("counts"),
                        app_version=m.get("app_version"), files=len(m.get("files", {})))
        except (BackupError, zipfile.BadZipFile) as e:
            item.update(error=str(e))
        out.append(item)
    return out


def prune(label: str = "auto", keep: int = AUTO_KEEP) -> List[str]:
    """Delete the oldest backups with this label beyond `keep`. Manual backups are never pruned."""
    mine = [b for b in list_backups() if b.get("label") == label]
    removed = []
    for b in mine[keep:]:
        os.remove(os.path.join(backups_dir(), b["name"]))
        removed.append(b["name"])
    if removed:
        logger.info("Removed %d old %s backup(s).", len(removed), label)
    return removed


def auto_backup_if_due(hours: int = 24) -> Optional[Dict[str, Any]]:
    """Create an "auto" backup if the newest one is older than `hours` (keeps the last 7)."""
    if not os.path.exists(_db_path()):
        return None
    newest = next((b for b in list_backups() if b.get("label") == "auto" and b.get("created_at")), None)
    if newest:
        try:
            created = datetime.fromisoformat(newest["created_at"])
            if datetime.now().astimezone() - created < timedelta(hours=hours):
                return None
        except ValueError:
            pass
    m = create("auto")
    prune("auto")
    return m


def backend_running(port: Optional[int] = None) -> bool:
    port = port or get_settings().PORT
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def restore(path: str, force: bool = False) -> Dict[str, Any]:
    """Replace the current data with a backup. A pre-restore backup is made first."""
    settings = get_settings()
    m = verify(path)
    if not force and backend_running():
        raise BackupError(f"Agent KitKat is running on port {settings.PORT}. Stop it first (stop.bat), then restore.")

    safety = create("pre-restore") if os.path.exists(_db_path()) else None

    with tempfile.TemporaryDirectory(prefix="kk_restore_") as tmp, zipfile.ZipFile(path) as z:
        z.extractall(tmp)   # every member name was checked by verify()
        db = _db_path()
        os.makedirs(os.path.dirname(db), exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(db + suffix):
                os.remove(db + suffix)
        shutil.copy2(os.path.join(tmp, "database.sqlite"), db)
        for arc, key in DIRS:
            target = getattr(settings, key)
            if os.path.isdir(target):
                shutil.rmtree(target)
            src = os.path.join(tmp, arc)
            if os.path.isdir(src):
                shutil.copytree(src, target)
            else:
                os.makedirs(target, exist_ok=True)
        if os.path.exists(os.path.join(tmp, "profile_seed.json")):
            shutil.copy2(os.path.join(tmp, "profile_seed.json"), settings.PROFILE_SEED_FILE)

    logger.warning("Restored backup %s (safety copy: %s)", os.path.basename(path), safety and safety["name"])
    return {"restored": os.path.basename(path), "counts": m.get("counts"), "created_at": m.get("created_at"),
            "safety_backup": safety and safety["name"]}


# ------------------------------------------------------------------------------ CLI
def _resolve(arg: str) -> str:
    if os.path.exists(arg):
        return arg
    candidate = os.path.join(backups_dir(), arg)
    if os.path.exists(candidate):
        return candidate
    raise BackupError(f"Backup not found: {arg}")


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(prog="python -m backend.maintenance.backup", description="Agent KitKat backup and restore")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="make a backup now")
    c.add_argument("--label", default="manual")
    sub.add_parser("list", help="list backups")
    v = sub.add_parser("verify", help="check a backup")
    v.add_argument("backup")
    r = sub.add_parser("restore", help="replace current data with a backup")
    r.add_argument("backup")
    r.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    r.add_argument("--force", action="store_true", help="restore even if the backend seems to be running")
    a = p.parse_args(argv)

    try:
        if a.cmd == "create":
            m = create(a.label)
            print(f"Created {m['path']} ({m['size'] / 1e6:.1f} MB)")
            print("Records:", ", ".join(f"{k} {v}" for k, v in m["counts"].items() if v is not None))
        elif a.cmd == "list":
            items = list_backups()
            if not items:
                print(f"No backups in {backups_dir()}")
            for b in items:
                counts = b.get("counts") or {}
                print(f"{b['name']}  {b['size'] / 1e6:6.1f} MB  {b.get('created_at', '?')}  "
                      f"jobs {counts.get('jobs', '?')}, applications {counts.get('applications', '?')}"
                      + (f"  ERROR: {b['error']}" if b.get("error") else ""))
        elif a.cmd == "verify":
            m = verify(_resolve(a.backup))
            print(f"OK: {len(m['files'])} files, checksums match, database intact (made {m.get('created_at')}).")
        elif a.cmd == "restore":
            path = _resolve(a.backup)
            m = verify(path)
            print(f"Backup from {m.get('created_at')}:",
                  ", ".join(f"{k} {v}" for k, v in (m.get('counts') or {}).items() if v is not None))
            if not a.yes:
                ans = input("This replaces your current database, resumes, applications and screenshots.\n"
                            "A pre-restore backup is made first. Type RESTORE to continue: ")
                if ans.strip() != "RESTORE":
                    print("Cancelled.")
                    return 1
            out = restore(path, force=a.force)
            print(f"Restored. Your previous data was saved as {out['safety_backup']}." if out["safety_backup"] else "Restored.")
        return 0
    except BackupError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
