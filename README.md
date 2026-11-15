# 🍫 Agent KitKat – Autonomous AI Career Assistant
> **Tagline:** Your little buddy for finding your next opportunity.

Agent KitKat is a personal, fully autonomous AI career assistant designed to discover jobs, evaluate eligibility, compare opportunities against your verified resume, draft applications, and automate form submissions under human supervision.

---

## ⚡ Key Highlights
- **100% Free & Local AI:** Powered by local [Ollama](https://ollama.ai) with `qwen2.5:1.5b`. Strictly ₹0 operating budget, zero external AI API costs.
- **Privacy First:** Resumes and personal profile data never leave your local machine.
- **Dual Operating Modes:**
  - **Mode A (Autonomous Daily Job Hunting):** Discovers jobs, verifies eligibility, scores resumes, and prepares applications.
  - **Mode B (Manual Job URL Analysis):** Instant one-click analysis of pasted job links.
- **Human-in-the-Loop:** Strict authorization policies (Manual Approval, Pre-authorized, Prepare Only).

---

## 🏗️ Project Architecture Overview

```
Agent_KitKat/
├── backend/
│   ├── main.py                     # FastAPI application entrypoint & API routes
│   ├── config.py                   # Centralized configuration (pydantic-settings)
│   ├── requirements.txt            # Python dependencies
│   ├── database/                   # SQLite database & SQLAlchemy ORM
│   │   ├── db.py                   # Async database engine & session dependency
│   │   └── models.py               # UserProfile and Resume tables
│   ├── routers/                    # API route controllers
│   │   ├── profile_router.py       # Profile CRUD endpoints
│   │   ├── resume_router.py        # Resume upload, parse, list, and activate
│   │   └── job_router.py           # Mode B job analysis (URL, text, file)
│   ├── schemas/                    # Pydantic data schemas
│   │   ├── health.py               # Health & Ollama connection models
│   │   ├── ai.py                   # AI prompt & generation models
│   │   ├── profile.py              # Personal profile & preferences models
│   │   ├── resume.py               # Resume metadata & extracted sections models
│   │   └── job.py                  # Job analysis request & structured details models
│   ├── services/                   # Core business logic services
│   │   ├── ollama_service.py       # Async Ollama client with retry & timeout handling
│   │   ├── profile_service.py      # Profile retrieval & update logic
│   │   ├── resume_service.py       # Resume persistence & verification sync
│   │   └── job_service.py          # Job URL scraping & text processing
│   ├── agents/                     # Specialized AI agents
│   │   └── job_reader.py           # Job Description Reader Agent (Qwen2.5 + regex)
│   └── tools/                      # Reusable tool modules
│       ├── resume_parser.py        # PDF/DOCX text & skill extraction engine
│       └── url_reader.py           # Web scraper with bot-wall protection detection
├── storage/                        # Secure local storage (resumes, drafts, logs)
│   ├── agent_kitkat.db             # Local SQLite database
│   ├── resumes/                    # Stored resume documents
│   ├── applications/
│   └── logs/
├── tests/                          # Automated verification tests
│   ├── test_phase1.py              # In-process ASGI integration tests
│   ├── test_phase2.py              # Profile & resume parser integration tests
│   ├── test_phase3.py              # Mode B job analysis tests
│   └── test_live_server.py         # Live TCP socket HTTP server tests
├── .env.example                    # Environment variable template
├── .gitignore                      # Git ignore patterns
└── README.md                       # Master documentation
```

---

## 🚀 Quickstart Guide (Phase 1)

### 1. Prerequisites
- **Python:** 3.10+ (Verified on Python 3.13.7)
- **Ollama:** Installed and running locally
- **Ollama Model:** `qwen2.5:1.5b`
  ```powershell
  ollama pull qwen2.5:1.5b
  ```

### 2. Setup Virtual Environment
```powershell
# From project root: f:\Agent_KitKat
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

### 3. Start the Backend Server
```powershell
.\venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at:
- **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- **AI Test Endpoint:** `POST http://127.0.0.1:8000/api/ai/test`

---

## 🧪 Testing

To run the automated test suites:
```powershell
# Phase 1: In-process ASGI tests (Health & Ollama)
.\venv\Scripts\python.exe tests\test_phase1.py

# Phase 2: Profile & Resume Parser integration tests
.\venv\Scripts\python.exe tests\test_phase2.py

# Phase 3: Mode B Job URL & Text Analysis tests
.\venv\Scripts\python.exe tests\test_phase3.py

# Live TCP HTTP server test
.\venv\Scripts\python.exe tests\test_live_server.py
```
