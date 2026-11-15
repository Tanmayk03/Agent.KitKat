"""
Import and Register Tanmay Kapoor's Real Resume into Agent KitKat.
Generates a professional PDF resume matching the attached resume, parses it,
registers it in the SQLite database, and updates the candidate ground-truth profile.
"""

import os
import sys
import asyncio
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Add project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database.db import AsyncSessionLocal, init_db
from backend.database.models import UserProfile, Resume
from backend.services.resume_service import ResumeService
from backend.services.profile_service import ProfileService
from backend.config import get_settings

settings = get_settings()


def generate_tanmay_resume_pdf(output_path: str):
    """Generate high-quality PDF resume matching Tanmay Kapoor's attached document."""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    name_style = ParagraphStyle(
        'Name',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a")
    )

    contact_style = ParagraphStyle(
        'Contact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#334155")
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=2
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1e293b")
    )

    bold_label = ParagraphStyle(
        'BoldLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0f172a")
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        leftIndent=12,
        textColor=colors.HexColor("#334155")
    )

    story = []

    # Header: Name & Contact
    story.append(Paragraph("Tanmay Kapoor", name_style))
    story.append(Spacer(1, 4))
    contact_line = (
        "+91-7905170353 | tanmaykapoor003@gmail.com | "
        "linkedin.com/in/tanmay-kapoor | github.com/tanmayk03 | tanmayk.tech"
    )
    story.append(Paragraph(contact_line, contact_style))
    story.append(Spacer(1, 6))

    # Divider line
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceBefore=1, spaceAfter=6))

    # Summary
    story.append(Paragraph("Summary", section_heading))
    summary_text = (
        "Computer Science undergraduate with hands-on experience in full-stack software development, backend engineering, "
        "SQL, and cloud deployment. Experienced in building and deploying scalable web applications using React.js, Node.js, "
        "Express.js, and MongoDB. Strong foundation in Data Structures, Algorithms, Object-Oriented Programming, REST APIs, "
        "Operating Systems, Computer Networks, debugging, and SDLC. Experienced in translating requirements into technical "
        "solutions and delivering production-oriented applications through end-to-end development."
    )
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 4))

    # Skills Section
    story.append(Paragraph("Skills", section_heading))
    skills_data = [
        "<b>Programming:</b> Java, JavaScript, Python, C++, SQL",
        "<b>Frontend:</b> React.js, Redux, Vite, Tailwind CSS, HTML, CSS",
        "<b>Backend:</b> Node.js, Express.js, REST APIs, Redis, JWT, CORS",
        "<b>Databases:</b> MySQL, MongoDB, Firebase Firestore, Supabase",
        "<b>Testing & Software Engineering:</b> Jest, Supertest, Postman, API Testing, Debugging, SDLC",
        "<b>Core CS:</b> Data Structures & Algorithms, OOP, DBMS, Operating Systems, Computer Networks, Problem Solving",
        "<b>Cloud & DevOps:</b> Microsoft Azure, Docker, GitHub Actions, CI/CD, Git, GitHub"
    ]
    for sk in skills_data:
        story.append(Paragraph(sk, body_style))
        story.append(Spacer(1, 1.5))
    story.append(Spacer(1, 4))

    # Experience Section
    story.append(Paragraph("Experience", section_heading))

    # GateBuddy
    exp1_header = Table(
        [
            [Paragraph("<b>GateBuddy</b> — Community & Technology Lead", bold_label),
             Paragraph("Remote | Apr 2026 – Present", ParagraphStyle('R', parent=body_style, alignment=TA_RIGHT))]
        ],
        colWidths=[360, 170]
    )
    exp1_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
    story.append(exp1_header)
    story.append(Paragraph("• Identified campus coordination challenges and built a platform serving 200+ active users, translating operational requirements into product workflows and technical solutions.", bullet_style))
    story.append(Paragraph("• Designed and developed the platform using React.js, Node.js, Express.js, and MongoDB, implementing authentication, RESTful APIs, order lifecycle management, and geo-aware filtering.", bullet_style))
    story.append(Paragraph("• Owned end-to-end product development from requirements and implementation to deployment, debugging, and operational improvement, while coordinating a 10-member student team.", bullet_style))
    story.append(Spacer(1, 4))

    # Decrypton
    exp2_header = Table(
        [
            [Paragraph("<b>Decrypton</b> — Application Development Intern", bold_label),
             Paragraph("Remote | May 2025 – Aug 2025", ParagraphStyle('R', parent=body_style, alignment=TA_RIGHT))]
        ],
        colWidths=[360, 170]
    )
    exp2_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
    story.append(exp2_header)
    story.append(Paragraph("• Built and integrated RESTful APIs using Node.js and Express.js across 4+ core application modules, enabling reliable frontend-backend communication.", bullet_style))
    story.append(Paragraph("• Developed responsive interfaces using React.js, Tailwind CSS, Vite, and Redux, and structured MongoDB schemas for frontend-backend data integration.", bullet_style))
    story.append(Spacer(1, 4))

    # Projects Section
    story.append(Paragraph("Projects", section_heading))

    # Project 1: Hyperlocal Delivery Application
    p1_header = Table(
        [
            [Paragraph("<b>Hyperlocal Delivery Application</b> (React.js, Redux, Node.js, Express.js, MongoDB, Tailwind CSS)", bold_label),
             Paragraph("GitHub | Live Demo", ParagraphStyle('R', parent=body_style, alignment=TA_RIGHT))]
        ],
        colWidths=[400, 130]
    )
    p1_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
    story.append(p1_header)
    story.append(Paragraph("• Developed a full-stack commerce platform supporting product catalog browsing, cart management, checkout, and end-to-end order tracking.", bullet_style))
    story.append(Paragraph("• Implemented RESTful backend services for authentication, inventory queries, cart operations, and order processing.", bullet_style))
    story.append(Paragraph("• Built responsive interfaces using React.js, Redux, and Tailwind CSS, integrating backend APIs for application data and product recommendations.", bullet_style))
    story.append(Spacer(1, 4))

    # Project 2: MargSense
    p2_header = Table(
        [
            [Paragraph("<b>MargSense – Bengaluru Traffic Management Platform</b> (React.js, Tailwind CSS, Python, FastAPI, Scikit-learn, Docker, Azure, CI/CD)", bold_label),
             Paragraph("GitHub", ParagraphStyle('R', parent=body_style, alignment=TA_RIGHT))]
        ],
        colWidths=[440, 90]
    )
    p2_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
    story.append(p2_header)
    story.append(Paragraph("• Developed a full-stack traffic monitoring platform integrating a React.js frontend with Python-based backend services for traffic hotspot and violation insights.", bullet_style))
    story.append(Paragraph("• Built FastAPI REST endpoints to process traffic datasets and serve prediction results to the frontend, enabling frontend-backend integration.", bullet_style))
    story.append(Paragraph("• Containerized the application using Docker and deployed it on Microsoft Azure, using GitHub Actions to automate build and deployment workflows.", bullet_style))
    story.append(Spacer(1, 4))

    # Education Section
    story.append(Paragraph("Education", section_heading))
    edu1 = Table(
        [
            [Paragraph("<b>SRM University, Delhi NCR</b> — B.Tech in Computer Science (Data Science)", bold_label),
             Paragraph("India | Aug 2023 – May 2027", ParagraphStyle('R', parent=body_style, alignment=TA_RIGHT))],
            [Paragraph("CGPA: <b>8.53</b>", body_style), Paragraph("", body_style)]
        ],
        colWidths=[380, 150]
    )
    edu1.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
    story.append(edu1)
    story.append(Spacer(1, 3))

    edu2 = Table(
        [
            [Paragraph("<b>SKD Academy</b> — Senior Secondary (ICSE)", bold_label),
             Paragraph("India | 2021 – 2023", ParagraphStyle('R', parent=body_style, alignment=TA_RIGHT))]
        ],
        colWidths=[380, 150]
    )
    edu2.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
    story.append(edu2)
    story.append(Spacer(1, 4))

    # Certifications & Achievements
    story.append(Paragraph("Certifications & Achievements", section_heading))
    certs = [
        "• Oracle OCI 2025 Data Science Professional",
        "• MongoDB Associate Developer",
        "• Microsoft Azure AI Essentials",
        "• Career Essentials in Generative AI",
        "• 1st Place – App Development Competition",
        "• Flipkart Gridlock 2.0 – Selected for Round 2"
    ]
    for c in certs:
        story.append(Paragraph(c, bullet_style))
        story.append(Spacer(1, 1))

    doc.build(story)
    print(f"✅ Generated Tanmay Kapoor's Resume PDF at: {output_path}")


async def register_tanmay_profile_and_resume():
    """Update database profile with Tanmay's details and register active resume."""
    await init_db()

    os.makedirs(settings.RESUMES_DIR, exist_ok=True)
    pdf_filename = "Tanmay_Kapoor_Resume.pdf"
    pdf_path = os.path.join(settings.RESUMES_DIR, pdf_filename)

    # 1. Generate PDF
    generate_tanmay_resume_pdf(pdf_path)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    async with AsyncSessionLocal() as session:
        # 2. Register and parse resume in ResumeService
        resume_record, profile, verified = await ResumeService.save_and_parse_resume(
            session=session,
            file_name=pdf_filename,
            file_bytes=pdf_bytes
        )
        print(f"✅ Saved and parsed Resume ID: {resume_record.id}")
        print(f"Verified Skills count: {len(verified)}")

        # 3. Set as active resume
        await ResumeService.set_active_resume(session, resume_record.id)
        print("✅ Resume set as active.")

        # 4. Update Profile with full details
        profile.full_name = "Tanmay Kapoor"
        profile.email = "tanmaykapoor003@gmail.com"
        profile.phone = "+91-7905170353"
        profile.location = "Delhi NCR, India"
        profile.linkedin_url = "https://linkedin.com/in/tanmay-kapoor"
        profile.github_url = "https://github.com/tanmayk03"
        profile.portfolio_url = "https://tanmayk.tech"

        profile.education = {
            "degree": "B.Tech",
            "specialization": "Computer Science (Data Science)",
            "college": "SRM University, Delhi NCR",
            "cgpa": 8.53,
            "graduation": "May 2027",
            "graduation_year": 2027
        }

        profile.preferred_roles = [
            "Software Engineer Intern",
            "Software Developer Intern",
            "Frontend Developer Intern",
            "Full Stack Developer Intern",
            "Backend Developer Intern",
            "AI/ML Intern",
            "Data Engineer Intern"
        ]

        profile.preferred_locations = [
            "India",
            "Remote",
            "Bangalore",
            "Noida",
            "Delhi NCR"
        ]

        profile.expected_stipend = "Market Rate / Negotiable"
        profile.work_mode = "Any"

        profile.projects = [
            {
                "title": "Hyperlocal Delivery Application",
                "description": "Full-stack commerce platform supporting product catalog browsing, cart management, checkout, and end-to-end order tracking with RESTful services.",
                "technologies": ["React.js", "Redux", "Node.js", "Express.js", "MongoDB", "Tailwind CSS"],
                "links": ["https://github.com/tanmayk03", "Live Demo"]
            },
            {
                "title": "MargSense – Bengaluru Traffic Management Platform",
                "description": "Full-stack traffic monitoring platform integrating React.js frontend with Python/FastAPI backend, ML predictions, Docker, Azure cloud deployment, and GitHub Actions CI/CD.",
                "technologies": ["React.js", "Tailwind CSS", "Python", "FastAPI", "Scikit-learn", "Docker", "Microsoft Azure", "CI/CD"],
                "links": ["https://github.com/tanmayk03"]
            }
        ]

        profile.work_experience = [
            {
                "company": "GateBuddy",
                "role": "Community & Technology Lead",
                "duration": "Apr 2026 – Present",
                "location": "Remote",
                "description": "Built campus platform serving 200+ active users using React.js, Node.js, Express.js, MongoDB, order lifecycle management, coordinating 10-member student team."
            },
            {
                "company": "Decrypton",
                "role": "Application Development Intern",
                "duration": "May 2025 – Aug 2025",
                "location": "Remote",
                "description": "Built and integrated RESTful APIs using Node.js/Express.js across 4+ core application modules. Responsive React.js/Tailwind interfaces and MongoDB integration."
            }
        ]

        profile.certifications = [
            "Oracle OCI 2025 Data Science Professional",
            "MongoDB Associate Developer",
            "Microsoft Azure AI Essentials",
            "Career Essentials in Generative AI",
            "1st Place – App Development Competition",
            "Flipkart Gridlock 2.0 – Selected for Round 2"
        ]

        # Verified skills from resume
        tanmay_skills = [
            "Python", "JavaScript", "Java", "C++", "SQL",
            "React.js", "React", "Redux", "Vite", "Tailwind CSS", "HTML", "CSS",
            "Node.js", "Express.js", "REST APIs", "Redis", "JWT", "CORS",
            "MySQL", "MongoDB", "Firebase Firestore", "Supabase",
            "Jest", "Supertest", "Postman", "API Testing", "Debugging", "SDLC",
            "Data Structures & Algorithms", "OOP", "DBMS", "Operating Systems", "Computer Networks", "Problem Solving",
            "Microsoft Azure", "Docker", "GitHub Actions", "CI/CD", "Git", "GitHub", "FastAPI", "Scikit-learn"
        ]
        profile.verified_skills = tanmay_skills
        profile.unverified_skills = []

        await session.commit()
        await session.refresh(profile)

        print("\n==================================================")
        print("🎉 TANMAY KAPOOR PROFILE & RESUME INITIALIZED!")
        print("==================================================")
        print(f"Candidate:    {profile.full_name}")
        print(f"Email:        {profile.email}")
        print(f"Phone:        {profile.phone}")
        print(f"College:      {profile.education['college']}")
        print(f"Degree:       {profile.education['degree']} ({profile.education['specialization']})")
        print(f"CGPA:         {profile.education['cgpa']}")
        print(f"Graduation:   {profile.education['graduation']} ({profile.education['graduation_year']})")
        print(f"Active Resume: {resume_record.file_name} (ID: {resume_record.id})")
        print(f"Verified Skills ({len(profile.verified_skills)}): {', '.join(profile.verified_skills[:8])}...")
        print("==================================================")


if __name__ == "__main__":
    asyncio.run(register_tanmay_profile_and_resume())
