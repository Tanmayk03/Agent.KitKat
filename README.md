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
│   ├── schemas/                    # Pydantic data schemas
│   │   ├── health.py               # Health & Ollama connection models
│   │   └── ai.py                   # AI prompt & generation models
│   └── services/                   # Core backend services
│       └── ollama_service.py       # Async Ollama client with retry & timeout handling
├── storage/                        # Secure local storage (resumes, drafts, logs)
│   ├── resumes/
│   ├── applications/
│   └── logs/
├── tests/                          # Automated verification tests
│   ├── test_phase1.py              # In-process ASGI integration tests
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

## 🧪 Testing Phase 1

To run the automated test suites:
```powershell
# In-process ASGI tests
.\venv\Scripts\python.exe tests\test_phase1.py

# Live TCP HTTP server test
.\venv\Scripts\python.exe tests\test_live_server.py
```
