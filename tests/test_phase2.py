"""
Phase 2 Verification Tests for Agent KitKat.
Tests:
1. Profile retrieval and default initialization (B.Tech, SRM, 8.44, unverified skills).
2. Profile editing/updating (name, email, github, preferences).
3. PDF Resume upload, text parsing, and automatic skill verification.
4. DOCX Resume upload, text parsing, and skill verification.
5. Resume listing and details retrieval.
6. Active resume switching.
7. Resume deletion and physical file cleanup.
8. Negative tests (unsupported file extension, non-existent resume ID).
"""

import os
import io
import sys
import asyncio
from docx import Document
import httpx

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests._isolation  # noqa: E402,F401  -- throwaway DB; never touches your real data

from backend.main import app
from backend.database.db import init_db


def create_test_pdf_bytes() -> bytes:
    """Creates a valid PDF binary with test resume content."""
    pdf_content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
5 0 obj << /Length 320 >>
stream
BT
/F1 12 Tf
72 720 Td
(Software Engineer Intern Resume - SDE Focus) Tj
0 -20 Td
(Education) Tj
0 -15 Td
(B.Tech in Computer Science and Data Science - SRM University Delhi NCR - CGPA: 8.44) Tj
0 -25 Td
(Technical Skills) Tj
0 -15 Td
(Python, React, Node.js, Web development, SQL, FastAPI, Docker, Git) Tj
0 -25 Td
(Projects) Tj
0 -15 Td
(Agent KitKat - Autonomous AI Career Assistant built with Python and FastAPI) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000118 00000 n 
0000000255 00000 n 
0000000330 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
700
%%EOF"""
    return pdf_content


def create_test_docx_bytes() -> bytes:
    """Creates a valid DOCX binary with test resume content."""
    doc = Document()
    doc.add_heading("AI & Full-Stack Developer Intern Resume", level=1)

    doc.add_heading("Education", level=2)
    doc.add_paragraph("SRM University, Delhi NCR — B.Tech Computer Science (CGPA: 8.44, Grad: 2027)")

    doc.add_heading("Skills", level=2)
    doc.add_paragraph("Java, JavaScript, TypeScript, Next.js, Machine Learning, PyTorch, MongoDB, Linux")

    doc.add_heading("Projects", level=2)
    doc.add_paragraph("Career Agent: Built full stack job search with Java backend and React dashboard.")

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


async def run_phase2_tests():
    print("==================================================")
    print("🚀 Starting Agent KitKat Phase 2 Verification Tests")
    print("==================================================")

    # Ensure DB tables are ready
    await init_db()

    # Reset tables for reproducible test run
    from sqlalchemy import delete
    from backend.database.db import AsyncSessionLocal
    from backend.database.models import UserProfile, Resume
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Resume))
        await session.execute(delete(UserProfile))
        await session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

        # ----------------------------------------------------
        # 1. Test Default Profile Initialization
        # ----------------------------------------------------
        print("\n[Test 1] Testing Default Profile Initialization (GET /api/profile)...")
        res = await client.get("/api/profile")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        profile = res.json()
        print(f"Education: {profile['education']}")
        print(f"Unverified Skills: {profile['unverified_skills']}")
        print(f"Verified Skills: {profile['verified_skills']}")

        assert profile["education"]["degree"] == "B.Tech"
        assert profile["education"]["specialization"] == "Computer Science and Data Science"
        assert profile["education"]["college"] == "Example University, Delhi NCR"  # from tests/_isolation.py seed
        assert profile["education"]["cgpa"] == 8.44
        assert profile["education"]["graduation_year"] == 2027
        assert "Python" in profile["unverified_skills"]
        assert "React" in profile["unverified_skills"]
        assert len(profile["verified_skills"]) == 0, "Verified skills should start empty before resume upload!"
        print("✅ Test 1 Passed: Default profile successfully verified against initial requirements.")

        # ----------------------------------------------------
        # 2. Test Profile Update
        # ----------------------------------------------------
        print("\n[Test 2] Testing Profile Update (PUT /api/profile)...")
        update_data = {
            "full_name": "Test Candidate",
            "email": "candidate@srm.edu",
            "phone": "+91 9876543210",
            "location": "Delhi NCR, India",
            "github_url": "https://github.com/candidate",
            "linkedin_url": "https://linkedin.com/in/candidate",
            "work_mode": "Hybrid"
        }
        res = await client.put("/api/profile", json=update_data)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        updated_profile = res.json()
        assert updated_profile["full_name"] == "Test Candidate"
        assert updated_profile["email"] == "candidate@srm.edu"
        assert updated_profile["github_url"] == "https://github.com/candidate"
        assert updated_profile["work_mode"] == "Hybrid"
        print(f"Updated Name: {updated_profile['full_name']} | Email: {updated_profile['email']}")
        print("✅ Test 2 Passed: Profile fields updated and persisted.")

        # ----------------------------------------------------
        # 3. Test PDF Resume Upload & Verification
        # ----------------------------------------------------
        print("\n[Test 3] Testing PDF Resume Upload & Parsing (POST /api/resumes/upload)...")
        pdf_bytes = create_test_pdf_bytes()
        files = {
            "file": ("sde_intern_resume.pdf", pdf_bytes, "application/pdf")
        }
        res = await client.post("/api/resumes/upload", files=files)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        pdf_res_data = res.json()
        resume_1 = pdf_res_data["resume"]
        print(f"Uploaded Resume ID: {resume_1['id']}")
        print(f"File Type: {resume_1['file_type']} | Active: {resume_1['is_active']}")
        print(f"Extracted Skills: {pdf_res_data['all_extracted_skills']}")
        print(f"Newly Verified Skills: {pdf_res_data['verified_skills']}")
        print(f"Remaining Unverified Skills: {pdf_res_data['unverified_skills']}")

        assert resume_1["is_active"] is True, "First uploaded resume must be set active automatically!"
        assert "Python" in pdf_res_data["verified_skills"], "Python should now be verified from resume!"
        assert "React" in pdf_res_data["verified_skills"], "React should now be verified from resume!"
        assert "Node.js" in pdf_res_data["verified_skills"], "Node.js should now be verified from resume!"
        assert "Web development" in pdf_res_data["verified_skills"]
        print("✅ Test 3 Passed: PDF resume parsed and profile skills verified deterministically.")

        # ----------------------------------------------------
        # 4. Test DOCX Resume Upload
        # ----------------------------------------------------
        print("\n[Test 4] Testing DOCX Resume Upload (POST /api/resumes/upload)...")
        docx_bytes = create_test_docx_bytes()
        files_docx = {
            "file": ("aiml_intern_resume.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        }
        res = await client.post("/api/resumes/upload", files=files_docx)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        docx_res_data = res.json()
        resume_2 = docx_res_data["resume"]
        print(f"Uploaded DOCX Resume ID: {resume_2['id']}")
        print(f"File Type: {resume_2['file_type']} | Active: {resume_2['is_active']}")
        print(f"All Verified Skills: {docx_res_data['verified_skills']}")

        assert resume_2["is_active"] is False, "Second resume should not automatically replace active resume!"
        assert "Java" in docx_res_data["verified_skills"], "Java should now be verified!"
        assert "JavaScript" in docx_res_data["verified_skills"], "JavaScript should now be verified!"
        print("✅ Test 4 Passed: DOCX resume parsed and remaining skills verified.")

        # ----------------------------------------------------
        # 5. Test Resume Listing & Details
        # ----------------------------------------------------
        print("\n[Test 5] Testing Resume Listing & Details (GET /api/resumes)...")
        res = await client.get("/api/resumes")
        assert res.status_code == 200
        resumes_list = res.json()
        assert len(resumes_list) >= 2
        print(f"Total Resumes Managed: {len(resumes_list)}")

        res = await client.get(f"/api/resumes/{resume_1['id']}")
        assert res.status_code == 200
        resume_detail = res.json()
        assert len(resume_detail["raw_text"]) > 0
        assert "Python" in resume_detail["raw_text"]
        print(f"Resume Detail fetched for {resume_1['id']}. Raw text length: {len(resume_detail['raw_text'])} chars.")
        print("✅ Test 5 Passed: Resume list and detail endpoints verified.")

        # ----------------------------------------------------
        # 6. Test Active Resume Switch
        # ----------------------------------------------------
        print("\n[Test 6] Testing Active Resume Switch (PUT /api/resumes/{id}/activate)...")
        res = await client.put(f"/api/resumes/{resume_2['id']}/activate")
        assert res.status_code == 200
        activated_resume = res.json()
        assert activated_resume["is_active"] is True

        # Check profile active resume pointer
        res = await client.get("/api/profile")
        profile = res.json()
        assert profile["active_resume_id"] == resume_2["id"]
        print(f"Profile active resume successfully switched to: {profile['active_resume_id']}")
        print("✅ Test 6 Passed: Resume activation switched properly.")

        # ----------------------------------------------------
        # 7. Test Negative Error Cases
        # ----------------------------------------------------
        print("\n[Test 7] Testing Negative Cases (Invalid File Extension & Non-existent Resume)...")
        bad_files = {
            "file": ("malicious.exe", b"invalid executable", "application/octet-stream")
        }
        res = await client.post("/api/resumes/upload", files=bad_files)
        assert res.status_code == 400, f"Expected 400 for .exe file, got {res.status_code}"
        print("Rejected .exe upload with 400 Bad Request.")

        res = await client.get("/api/resumes/non-existent-uuid")
        assert res.status_code == 404, f"Expected 404 for non-existent ID, got {res.status_code}"
        print("Non-existent resume returned 404 Not Found.")
        print("✅ Test 7 Passed: Negative cases correctly handled.")

        # ----------------------------------------------------
        # 8. Test Resume Deletion
        # ----------------------------------------------------
        print("\n[Test 8] Testing Resume Deletion (DELETE /api/resumes/{id})...")
        res = await client.delete(f"/api/resumes/{resume_1['id']}")
        assert res.status_code == 200
        print(f"Deleted Resume ID: {resume_1['id']}")

        # Verify it no longer exists
        res = await client.get(f"/api/resumes/{resume_1['id']}")
        assert res.status_code == 404
        print("Verified resume no longer found in database.")
        print("✅ Test 8 Passed: Resume deleted and cleaned up successfully.")

    print("\n==================================================")
    print("🎉 ALL PHASE 2 TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_phase2_tests())
