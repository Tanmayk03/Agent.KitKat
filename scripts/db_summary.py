"""
Read-only summary of your Agent KitKat database (counts, newest jobs, applications by stage).

    python scripts/db_summary.py

Opens the database read-only; it never changes anything.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.config import get_settings  # noqa: E402

path = get_settings().database_path
if not os.path.exists(path):
    sys.exit(f"No database yet at {path}. Start Agent KitKat once first.")
uri = "file:" + path.replace("\\", "/").replace("?", "%3F") + "?mode=ro"
if os.name == "nt" and not uri.startswith("file:/"):
    uri = "file:/" + uri[len("file:"):]
con = sqlite3.connect(uri, uri=True)

print(f"Database: {path}\n")
for t in ("jobs", "eligibility_results", "match_results", "application_drafts", "approval_requests",
          "applications", "resumes", "discovery_runs", "daily_reports"):
    try:
        print(f"{t:<22} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    except sqlite3.Error:
        print(f"{t:<22} (missing)")

print("\nApplications by stage:")
for stage, n in con.execute("SELECT COALESCE(stage, '?'), COUNT(*) FROM applications GROUP BY 1 ORDER BY 2 DESC"):
    print(f"  {stage:<22} {n}")

print("\nNewest 10 jobs:")
for title, company, source, status in con.execute(
        "SELECT title, company, source, status FROM jobs ORDER BY COALESCE(fetched_at, created_at) DESC LIMIT 10"):
    print(f"  {title} | {company} [{source}] {'(expired)' if status == 'expired' else ''}")
con.close()
