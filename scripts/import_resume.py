"""
Import YOUR real resume file (PDF or DOCX) into Agent KitKat from the command line.
Equivalent to uploading it on the Resumes page.

    python scripts/import_resume.py "C:\\path\\to\\My_Resume.pdf" [--activate]

Nothing is generated or invented: the file is parsed as-is, and only skills that are
literally present in it are marked as verified.
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.db import AsyncSessionLocal, init_db  # noqa: E402
from backend.services.resume_service import ResumeService  # noqa: E402


async def main(path: str, activate: bool) -> None:
    await init_db()
    with open(path, "rb") as f:
        data = f.read()
    async with AsyncSessionLocal() as session:
        resume, profile, skills = await ResumeService.save_and_parse_resume(session, os.path.basename(path), data)
        if activate and not resume.is_active:
            await ResumeService.set_active_resume(session, resume.id)
    print(f"Imported {resume.file_name} (id {resume.id}).")
    print(f"Skills found in the file: {', '.join(skills) or 'none recognised'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path")
    parser.add_argument("--activate", action="store_true", help="make this the active resume")
    args = parser.parse_args()
    if not os.path.isfile(args.path):
        sys.exit(f"File not found: {args.path}")
    asyncio.run(main(args.path, args.activate))
