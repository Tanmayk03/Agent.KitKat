"""
Agent KitKat - Phase 8 Verification Test Suite
Verifies React + Tailwind CSS dashboard, all key application pages,
client API integration service, build artifacts, and asset pipeline.
"""

import os
import sys
import subprocess

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_frontend_files_exist():
    """Verify all required React components and pages are present."""
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

    required_files = [
        "package.json",
        "vite.config.js",
        "index.html",
        "src/index.css",
        "src/main.jsx",
        "src/App.jsx",
        "src/services/api.js",
        "src/components/Navbar.jsx",
        "src/pages/DashboardPage.jsx",
        "src/pages/AnalyzeJobPage.jsx",
        "src/pages/OpportunitiesPage.jsx",
        "src/pages/ApprovalsPage.jsx",
        "src/pages/TrackerPage.jsx",
        "src/pages/ProfilePage.jsx",
        "src/pages/ResumesPage.jsx",
        "src/pages/DailyReportsPage.jsx",
        "src/pages/SettingsPage.jsx",
    ]

    for rel_path in required_files:
        full_path = os.path.join(base, rel_path)
        assert os.path.exists(full_path), f"Missing required file: {rel_path}"

    print("✅ All 17 core frontend pages, components, and configs exist.")


def test_api_client_coverage():
    """Verify client API service contains methods for all required operations."""
    api_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "services", "api.js"))
    with open(api_file, "r", encoding="utf-8") as f:
        content = f.read()

    expected_methods = [
        "getHealth",
        "getProfile",
        "updateProfile",
        "getResumes",
        "uploadResume",
        "activateResume",
        "deleteResume",
        "analyzeJobUrl",
        "analyzeJobText",
        "analyzeJobFile",
        "getJobs",
        "evaluateJob",
        "getRankings",
        "prepareApplication",
        "getDraft",
        "updateDraft",
        "getApprovals",
        "decideApproval",
        "getTracker",
        "runBrowserAutomation",
        "emergencyStop",
        "getBrowserStatus",
        "triggerDiscovery",
        "getDiscoverySources",
        "getSchedulerStatus",
        "startScheduler",
        "stopScheduler",
        "triggerSchedulerNow",
        "getDailyReport",
        "getReportHistory",
    ]

    for method in expected_methods:
        assert f"{method}(" in content or f"{method}:" in content, f"Missing API method: {method}"

    print(f"✅ API client verified with all {len(expected_methods)} Phase 1-7 endpoint methods.")


def test_production_build_artifacts():
    """Verify production bundle exists and is valid."""
    dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
    assert os.path.exists(dist_dir), "frontend/dist does not exist"

    index_html = os.path.join(dist_dir, "index.html")
    assert os.path.exists(index_html), "dist/index.html does not exist"
    assert os.path.getsize(index_html) > 500

    assets_dir = os.path.join(dist_dir, "assets")
    assert os.path.exists(assets_dir), "dist/assets does not exist"
    asset_files = os.listdir(assets_dir)
    assert any(f.endswith(".js") for f in asset_files), "Missing compiled JS bundle"
    assert any(f.endswith(".css") for f in asset_files), "Missing compiled CSS stylesheet"

    print(f"✅ Production build verified: {len(asset_files)} asset files generated in dist/.")


if __name__ == "__main__":
    print("==================================================")
    print("🚀 Starting Agent KitKat Phase 8 Verification Tests")
    print("==================================================")
    test_frontend_files_exist()
    test_api_client_coverage()
    test_production_build_artifacts()
    print("==================================================")
    print("🎉 ALL PHASE 8 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")
