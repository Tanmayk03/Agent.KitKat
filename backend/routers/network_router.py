"""
Agent KitKat - Local Network Remote Access Router
Discovers local LAN IP address and provides connection endpoints
for remote iPhone PWA access over local Wi-Fi.
"""

import os
import socket
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, status
from pydantic import BaseModel

from backend.config import get_settings

logger = logging.getLogger("agent_kitkat.network_router")
settings = get_settings()

router = APIRouter(prefix="/api/network", tags=["Network & Mobile"])


class NetworkInfoResponse(BaseModel):
    hostname: str
    local_ip: str
    all_ips: List[str]
    frontend_port: int = 5173
    backend_port: int = 8000
    mobile_access_url: str
    setup_instructions: List[str]
    https: bool = False


def get_local_ip() -> str:
    """Determine the primary local IP address on the LAN."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually connect or send data, just routes to pick default interface
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip


@router.get(
    "/info",
    response_model=NetworkInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get local network IP and iPhone PWA connection instructions"
)
def get_network_info() -> NetworkInfoResponse:
    """Returns local LAN IP address and step-by-step instructions to connect an iPhone."""
    hostname = socket.gethostname()
    primary_ip = get_local_ip()

    # Collect all available IPv4 addresses
    all_ips = [primary_ip]
    try:
        _, _, ips = socket.gethostbyname_ex(hostname)
        for ip in ips:
            if ip not in all_ips and not ip.startswith("127."):
                all_ips.append(ip)
    except Exception:
        pass

    # The phone reaches the app through the frontend server started by start.bat (port 5173),
    # which listens on the LAN and forwards /api to this backend. It serves https when
    # frontend/certs/cert.pem + key.pem exist (mkcert, see docs/IPHONE.md).
    certs = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "certs")
    https = os.path.exists(os.path.join(certs, "cert.pem")) and os.path.exists(os.path.join(certs, "key.pem"))
    mobile_url = f"{'https' if https else 'http'}://{primary_ip}:5173"

    instructions = [
        "1. Start Agent KitKat with start.bat and keep both windows open (the frontend window is what your phone talks to).",
        "2. Connect your iPhone to the same Wi-Fi as this computer.",
        f"3. In Safari on the iPhone, open {mobile_url}",
        "4. Tap Share, then 'Add to Home Screen'.",
    ]
    if not https:
        instructions.append(
            "Over plain http the app works, but iOS won't keep an offline copy. For that, set up HTTPS with mkcert (docs/IPHONE.md)."
        )

    return NetworkInfoResponse(
        hostname=hostname,
        local_ip=primary_ip,
        all_ips=all_ips,
        frontend_port=5173,
        backend_port=settings.PORT,
        mobile_access_url=mobile_url,
        setup_instructions=instructions,
        https=https,
    )
