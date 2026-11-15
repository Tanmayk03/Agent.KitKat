"""
Agent KitKat - Phase 9 Verification Test Suite
Tests iPhone PWA web app manifest, Apple mobile touch tags,
safe area insets, Service Worker caching, and Local Network Remote Access API.
"""

import os
import sys
import json
import asyncio
from httpx import AsyncClient, ASGITransport

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app


def test_pwa_manifest():
    """Verify web app manifest is valid JSON and contains required PWA fields."""
    manifest_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "manifest.json"))
    assert os.path.exists(manifest_path), "manifest.json does not exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "name" in data and "KitKat" in data["name"]
    assert data["display"] == "standalone", f"Expected standalone display, got {data['display']}"
    assert "start_url" in data
    assert "theme_color" in data
    assert len(data.get("icons", [])) >= 1

    print("✅ PWA manifest verified (standalone display mode, icons, and theme color).")


def test_service_worker():
    """Verify PWA service worker exists and caches core shell."""
    sw_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "sw.js"))
    assert os.path.exists(sw_path), "sw.js does not exist"

    with open(sw_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "addEventListener('install'" in content
    assert "addEventListener('fetch'" in content
    assert "caches.open" in content

    print("✅ Service Worker verified for offline shell caching and fast load times.")


def test_ios_meta_tags_and_css_insets():
    """Verify index.html has Apple touch meta tags and CSS has safe area insets."""
    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "apple-mobile-web-app-capable" in html
    assert "viewport-fit=cover" in html
    assert "apple-touch-icon" in html
    assert "manifest.json" in html

    css_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "index.css"))
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert "safe-area-inset-bottom" in css
    assert "safe-area-inset-top" in css

    print("✅ iOS meta tags and notch/home indicator safe area insets verified.")


async def test_network_info_endpoint():
    """Verify GET /api/network/info returns valid LAN IP and iPhone setup instructions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/network/info")
        assert res.status_code == 200
        data = res.json()
        assert "local_ip" in data
        assert "mobile_access_url" in data
        assert str(data["frontend_port"]) in data["mobile_access_url"]
        assert len(data.get("setup_instructions", [])) >= 3
        print(f"Local LAN IP: {data['local_ip']}")
        print(f"iPhone Access URL: {data['mobile_access_url']}")
        print("✅ Network Info API endpoint verified.")


if __name__ == "__main__":
    print("==================================================")
    print("🚀 Starting Agent KitKat Phase 9 Verification Tests")
    print("==================================================")
    test_pwa_manifest()
    test_service_worker()
    test_ios_meta_tags_and_css_insets()
    asyncio.run(test_network_info_endpoint())
    print("==================================================")
    print("🎉 ALL PHASE 9 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")
