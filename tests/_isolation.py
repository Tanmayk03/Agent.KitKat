"""
Test isolation: point Agent KitKat at a throwaway database and storage folder.

MUST be imported before anything from `backend` (pytest does this via tests/conftest.py;
the standalone phase scripts import it right after their sys.path setup).

Without this, the tests used to run against storage/agent_kitkat.db and DELETE your real
jobs, resumes, drafts and application history.
"""

import atexit
import json
import os
import shutil
import sys
import tempfile

if any(name == "backend" or name.startswith("backend.") for name in sys.modules):
    raise RuntimeError(
        "tests._isolation was imported after backend modules; refusing to run tests against the real database."
    )

TEST_ROOT = tempfile.mkdtemp(prefix="kitkat_test_")
atexit.register(shutil.rmtree, TEST_ROOT, ignore_errors=True)

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + os.path.join(TEST_ROOT, "test.db").replace("\\", "/")
os.environ["STORAGE_DIR"] = TEST_ROOT
for key, sub in {
    "RESUMES_DIR": "resumes",
    "APPLICATIONS_DIR": "applications",
    "SCREENSHOTS_DIR": "screenshots",
    "LOGS_DIR": "logs",
}.items():
    os.environ[key] = os.path.join(TEST_ROOT, sub)

# Fictional test candidate (the real profile never lives in code)
TEST_PROFILE = {
    "full_name": "Test Candidate",
    "email": "test.candidate@example.com",
    "phone": "+91-0000000000",
    "location": "Delhi NCR, India",
    "education": {
        "degree": "B.Tech",
        "specialization": "Computer Science and Data Science",
        "college": "Example University, Delhi NCR",
        "cgpa": 8.44,
        "graduation": "May 2027",
        "graduation_year": 2027,
    },
    "preferred_roles": [
        "Software Engineer Intern", "Software Developer Intern", "Frontend Developer Intern",
        "AI/ML Intern", "Data Engineer Intern", "Full Stack Developer Intern",
    ],
    "preferred_locations": ["India", "Remote", "Bangalore", "Noida", "Delhi NCR"],
    "expected_stipend": "Market Rate / Negotiable",
    "unverified_skills": ["Python", "React", "Java", "JavaScript", "Node.js", "Web development"],
}
_seed_path = os.path.join(TEST_ROOT, "profile_seed.json")
with open(_seed_path, "w", encoding="utf-8") as f:
    json.dump(TEST_PROFILE, f)
os.environ["PROFILE_SEED_FILE"] = _seed_path

# Belt and braces: verify the backend really picked up the temp database.
from backend.config import get_settings  # noqa: E402

_settings = get_settings()
assert TEST_ROOT.replace("\\", "/") in _settings.DATABASE_URL, "Test DB isolation failed"
