"""
Backups from Settings (this computer only). Restoring is deliberately not available over the
API: it replaces all data, so it runs from restore.bat with Agent KitKat stopped.
"""

import asyncio
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.maintenance import backup
from backend.services import lan_access

router = APIRouter(prefix="/api/maintenance", tags=["Maintenance"])


def _require_local(request: Request) -> None:
    if not lan_access.is_local_request(request.client.host if request.client else None, request.headers):
        raise HTTPException(status_code=403, detail="Backups can only be managed on the computer running Agent KitKat.")


@router.get("/backups")
async def list_backups(request: Request):
    _require_local(request)
    items = await asyncio.to_thread(backup.list_backups)
    return {"folder": backup.backups_dir(), "items": items}


@router.post("/backups")
async def create_backup(request: Request):
    _require_local(request)
    try:
        m = await asyncio.to_thread(backup.create, "manual")
    except backup.BackupError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {k: m[k] for k in ("name", "size", "created_at", "counts")} | {"files": len(m["files"])}


@router.get("/backups/{name}")
async def download_backup(name: str, request: Request):
    _require_local(request)
    if not backup.NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid backup name.")
    path = os.path.join(backup.backups_dir(), name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Backup not found.")
    return FileResponse(path, media_type="application/zip", filename=name)
