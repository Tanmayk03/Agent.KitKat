# 🍫 Agent KitKat – Autonomous AI Career Assistant
> **Tagline:** Your little buddy for finding your next opportunity.  
> **Repository:** `Agent_KitKat` | **Budget:** Strictly ₹0 (Zero Paid APIs) | **Local AI:** Ollama `qwen2.5:1.5b`

---

## 📖 Executive Overview

**Agent KitKat** is a fully functional personal AI career assistant and autonomous job-hunting agent. Operating under strict human-in-the-loop policies with a strict ₹0 recurring budget, Agent KitKat runs 100% locally on your machine—protecting your privacy, your credentials, and your ground-truth personal profile.

It supports two primary operating modes:
- **Mode A (Autonomous Daily Job Hunting):** Scheduled multi-source opportunity discovery across Remotive, Jobicy, and Curated Tech Feeds, duplicate suppression, qualification verification, weighted resume matching, and automated application preparation.
- **Mode B (Manual Job URL Analysis):** Paste any job listing link (LinkedIn, Naukri, or career portal), raw description text, or upload a JD PDF/DOCX to extract structured requirements, verify eligibility, calculate resume match scores, and generate tailored cover letters instantly.

---

## ✨ Key Capabilities & System Features

| Feature | Description |
|---|---|
| **Zero-Budget Local AI** | Powered entirely by local [Ollama](https://ollama.ai) running `qwen2.5:1.5b` at `http://127.0.0.1:11434`. Zero OpenAI/Claude API costs. |
| **Ground Truth Profile** | Your profile is entered on the Profile page (or seeded from a git-ignored `profile_seed.json`). Nothing personal is hardcoded. Skills stay unverified until they are found in an uploaded resume. |
| **Deterministic Eligibility Engine** | Classifies degree, graduation batch, CGPA, work mode, and location strictly as `PASS`, `FAIL`, or `UNKNOWN`. Unknowns never pass; hard failures strictly override match scores. |
| **5-Factor Weighted Resume Matcher** | Transparent breakdown: Skills (35%), Education & Graduation (20%), Projects & Experience (20%), Role Relevance (15%), Location (10%). |
| **Tailored Application Preparation** | Synthesizes customized cover letters grounded in resume facts, formulates ATS screening answers, and maps standard form inputs. |
| **Human-approved submission** | **Manual Approval** (default) or **Prepare Only**. Nothing is submitted without your approval *and* a final per-application confirmation; the legacy "pre-authorized" policy is disabled. |
| **Playwright Browser Automation** | Auto-fills contact info, education, work auth, uploads active PDF resume, pastes cover letter, and verifies positive website receipt. |
| **Zero-Bypass Safety Compliance** | Immediately pauses upon encountering CAPTCHAs, Cloudflare Turnstiles, login walls, or sensitive legal declarations. Never attempts illegal bypass. |
| **Global Emergency Stop** | Instant kill-switch (`POST /api/browser/emergency-stop`) available in the dashboard navbar to cancel browser sessions instantly. |
| **Audited Daily Reporting** | Aggregates daily discovery and application counts directly from SQLite database tables (no fake statistics). |
| **Modern React 19 Dashboard** | Single Page Application styled with Tailwind CSS v4 and chocolate/amber dark theme. |
| **iPhone PWA & LAN Remote Access** | Installable Progressive Web Application with offline caching, notch/safe-area insets, and local Wi-Fi remote access. |

---

## 🏗️ Architecture & Project Structure

```
Agent_KitKat/
├── backend/
│   ├── main.py                     # FastAPI application entrypoint & static UI mount
│   ├── config.py                   # Centralized configuration (pydantic-settings)
│   ├── requirements.txt            # Python dependencies
│   ├── database/                   # SQLite database & SQLAlchemy ORM
│   │   ├── db.py                   # Async database engine & auto-migration
│   │   └── models.py               # UserProfile, Resume, Job, Drafts, Approvals, Reports
│   ├── routers/                    # API route controllers (30+ endpoints)
│   │   ├── profile_router.py       # Candidate profile CRUD
│   │   ├── resume_router.py        # PDF/DOCX resume upload, parse, and activate
│   │   ├── job_router.py           # Mode B job analysis (URL, text, file)
│   │   ├── matching_router.py      # Eligibility verification & resume matching
│   │   ├── application_router.py   # Draft preparation & human approval queue
│   │   ├── browser_router.py       # Playwright execution & emergency stop
│   │   ├── discovery_router.py     # Autonomous discovery & APScheduler controls
│   │   ├── reporting_router.py     # Daily activity report generation
│   │   └── network_router.py       # LAN IP discovery for iPhone remote access
│   ├── schemas/                    # Pydantic validation schemas
│   ├── services/                   # Core business logic services
│   │   ├── ollama_service.py       # Local Ollama AI client (with proxy-bypass)
│   │   ├── profile_service.py      # Profile management & ground-truth defaults
│   │   ├── resume_service.py       # Resume persistence & active switcher
│   │   ├── job_service.py          # Opportunity ingestion & feature extraction
│   │   ├── matching_service.py     # Weighted matching & ranking calculations
│   │   ├── application_service.py  # Cover letter synthesis & approval workflow
│   │   ├── browser_service.py      # Playwright browser automation coordinator
│   │   ├── discovery_service.py    # Multi-source job discovery pipeline
│   │   └── reporting_service.py    # Audited database report compiler
│   ├── agents/                     # Specialized AI agents
│   │   ├── job_reader.py           # Job Description Reader Agent
│   │   ├── eligibility_agent.py    # Deterministic Eligibility Verification Agent
│   │   ├── matching_agent.py       # 5-factor weighted resume matching engine
│   │   ├── application_agent.py    # Tailored Application Preparation Agent
│   │   └── browser_agent.py        # Playwright Browser Automation Agent
│   ├── scheduler/                  # APScheduler daily autonomous cron runner
│   └── tools/                      # Reusable toolkits (url_reader, duplicate_checker)
├── frontend/                       # Modern React 19 SPA
│   ├── index.html                  # Apple PWA meta tags & viewport insets
│   ├── package.json                # React 19, Tailwind CSS v4, Lucide Icons, Vite 8
│   ├── public/                     # PWA manifest.json & sw.js service worker
│   ├── dist/                       # Production compiled static bundle
│   └── src/
│       ├── services/api.js         # Unified client API adapter
│       ├── components/Navbar.jsx   # Header with AI status badge & Emergency Stop
│       └── pages/                  # 9 specialized application views
│           ├── DashboardPage.jsx
│           ├── AnalyzeJobPage.jsx
│           ├── OpportunitiesPage.jsx
│           ├── ApprovalsPage.jsx
│           ├── TrackerPage.jsx
│           ├── ProfilePage.jsx
│           ├── ResumesPage.jsx
│           ├── DailyReportsPage.jsx
│           └── SettingsPage.jsx
├── storage/                        # Persistent local directory
│   ├── agent_kitkat.db             # Local SQLite database
│   ├── resumes/                    # Stored resume documents
│   └── screenshots/                # Pre/post submission browser screenshots
├── tests/                          # 10 comprehensive test suites (Phases 1-10)
├── start_all.ps1                   # Master one-click PowerShell launcher
├── start_backend.ps1               # FastAPI backend launcher on port 8000
├── start_frontend.ps1              # Vite frontend dev server launcher on port 5173
├── run_all_tests.ps1               # Master test suite runner
└── PROGRESS.md                     # Detailed phase-by-phase development log
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Windows Laptop** (8 GB RAM, no NVIDIA GPU needed)
- **Python 3.10+** (Developed and verified on Python 3.13.7)
- **Node.js v18+** (Verified on Node v22.16.0)
- **Local Ollama Daemon:** Installed and running with `qwen2.5:1.5b`
  ```powershell
  ollama run qwen2.5:1.5b
  ```

### 2. Setup Environment
```powershell
# From project directory: F:\Agent_KitKat
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
playwright install chromium
```

### 3. Launch Agent KitKat

You can launch both the backend and frontend with a single command:
```powershell
.\start_all.ps1
```

Or run individual services:
- **Backend Server:**
  ```powershell
  .\start_backend.ps1
  ```
- **Frontend Dev Server:**
  ```powershell
  .\start_frontend.ps1
  ```

### 4. Access URLs
- **Web Dashboard (Dev Server):** [http://localhost:5173](http://localhost:5173)
- **Production UI (FastAPI Mounted):** [http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui)
- **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **System Health Endpoint:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- **iPhone (Local Wi-Fi):** `http://<your-lan-ip>:5173` (e.g. `http://172.20.10.4:5173`). The backend itself listens on 127.0.0.1 only; the Vite dev server proxies `/api`. Note: over plain `http://` on a LAN IP, iOS does not run service workers, so offline caching is unavailable; "Add to Home Screen" still works.

---

## 🏢 Finding India roles: follow company career boards

The free public feeds (Remotive, Jobicy, We Work Remotely, Arbeitnow, SimplifyJobs) carry very few
internships that are open to candidates in India. To cover the companies you actually want, go to
**Settings → Company Career Boards** and paste their careers URL:

* `https://boards.greenhouse.io/<company>` (Greenhouse)
* `https://jobs.lever.co/<company>` (Lever)
* `https://jobs.ashbyhq.com/<company>` (Ashby)

Agent KitKat reads these companies' official public job-board APIs on every discovery run, keeps
intern / fresher tech roles in India or open-remote, and marks jobs as expired when the company
takes them down. Each board appears in the dashboard's **Source Health** panel.

---

## 📱 iPhone PWA & Remote Access Setup

1. Connect your iPhone to the same local Wi-Fi network as your laptop.
2. In the Agent KitKat dashboard, navigate to **Settings** and view the **iPhone & Mobile Remote Access** card.
3. Open **Safari** on your iPhone and enter the displayed URL (e.g. `http://172.20.10.4:5173`).
4. Tap the **Share** button in Safari (box with upward arrow) and select **Add to Home Screen**.
5. Agent KitKat launches in standalone full-screen mode with native iOS gestures, bottom navigation, and safe-area notch adaptation.

---

## 🧪 Verification & Testing

### Test status
The previous "10/10 suites 100% PASS" table was not accurate. Current, executed results are in
`PROGRESS.md` (Stage 2) and the evidence-based feature status is in `FEATURE_STATUS.md`.

```powershell
.\venv\Scripts\python.exe -m pytest -q     # deterministic regression suite (mocks Ollama + job APIs)
.\run_all_tests.ps1                          # pytest + legacy phase scripts (Ollama / internet needed for some)
```
All tests use a throwaway database (`tests/_isolation.py`); they never touch `storage/agent_kitkat.db`.

---

## 🛡️ Ethics, Privacy & Compliance Commitments

1. **Zero Hallucination:** Candidate qualifications, degrees, skills, and projects are strictly sourced from verified profile data and uploaded resumes.
2. **Zero Bypass:** Anti-bot challenges (CAPTCHA, Turnstile) and login walls trigger safe pauses for human completion.
3. **Zero Financial Cost:** Purely local AI model inference ensures zero monthly recurring bills.
4. **Human Autonomy:** Submissions are governed strictly by the selected policy, backed by the global Emergency Stop kill-switch.
