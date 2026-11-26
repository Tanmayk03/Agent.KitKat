"""
Phone access (LAN token) endpoints.

* GET  /api/security/whoami             open: is this request local, and is it authorised?
* POST /api/security/pair               open: exchange the token for an HttpOnly cookie
* POST /api/security/unpair             clears the cookie on this device
* GET  /api/security/lan-access         this computer only: token, mode, pairing link
* POST /api/security/lan-access/rotate  this computer only: new token (paired phones must re-pair)
* POST /api/security/lan-access/mode    this computer only: "token" or "off"
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.services import lan_access

router = APIRouter(prefix="/api/security", tags=["Security"])

COOKIE_MAX_AGE = 365 * 24 * 3600


class PairRequest(BaseModel):
    token: str


class ModeRequest(BaseModel):
    mode: str


def _is_local(request: Request) -> bool:
    return lan_access.is_local_request(request.client.host if request.client else None, request.headers)


def _require_local(request: Request) -> None:
    if not _is_local(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only available on the computer running Agent KitKat.")


def _secure(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return proto.split(",")[0].strip() == "https"


@router.get("/whoami")
async def whoami(request: Request):
    local = _is_local(request)
    cfg = lan_access.load()
    authorised = local or (
        cfg["mode"] == "token"
        and lan_access.token_matches(lan_access.presented_token(request.headers, request.cookies))
    )
    return {"local": local, "authorized": authorised, "mode": cfg["mode"]}


@router.post("/pair")
async def pair(body: PairRequest, request: Request, response: Response):
    cfg = lan_access.load()
    if not _is_local(request) and cfg["mode"] == "off":
        raise HTTPException(status_code=403, detail="Phone access is turned off in Settings on your computer.")
    if not lan_access.token_matches(body.token.strip()):
        raise HTTPException(status_code=401, detail="That code is not valid. Scan the current QR code in Settings on your computer.")
    response.set_cookie(
        lan_access.TOKEN_COOKIE, body.token.strip(), max_age=COOKIE_MAX_AGE,
        httponly=True, samesite="strict", secure=_secure(request), path="/",
    )
    return {"paired": True}


@router.post("/unpair")
async def unpair(response: Response):
    response.delete_cookie(lan_access.TOKEN_COOKIE, path="/")
    return {"paired": False}


@router.get("/lan-access")
async def get_lan_access(request: Request, base_url: Optional[str] = None):
    """Token and pairing link. base_url: the phone address shown in Settings (http(s)://<ip>:5173)."""
    _require_local(request)
    cfg = lan_access.load()
    out = {"mode": cfg["mode"], "token": cfg["token"], "created_at": cfg.get("created_at")}
    if base_url and base_url.startswith(("http://", "https://")):
        out["pair_url"] = f"{base_url.rstrip('/')}/#pair={cfg['token']}"
    return out


@router.post("/lan-access/rotate")
async def rotate(request: Request):
    _require_local(request)
    cfg = lan_access.rotate_token()
    return {"mode": cfg["mode"], "token": cfg["token"], "created_at": cfg.get("created_at")}


@router.post("/lan-access/mode")
async def set_mode(body: ModeRequest, request: Request):
    _require_local(request)
    try:
        cfg = lan_access.set_mode(body.mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"mode": cfg["mode"]}
