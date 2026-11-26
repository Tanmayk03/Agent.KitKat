# Acceptance check: 1.0.0-rc.1 (2026-11-26)

The master prompt listed 20 acceptance criteria, but that list wasn't available when this check
was written. The table below is built from the prompt's mandatory rules and stage goals as they
were tracked through the work. If an original criterion is missing here, it still needs checking.

**Where things were verified**
* **Here** means the development sandbox (Linux):
  * real Chromium, real SQLite, and a real end-to-end run through the Vite proxy;
  * no Ollama;
  * only GitHub reachable on the internet.
* **Your PC** means it still needs to be run on your Windows machine (`.\test.ps1 -Live`, plus the
  manual steps listed below).

| # | Criterion | Evidence | Here | Your PC |
|---|---|---|---|---|
| 1 | One-step install and start on Windows | `install.bat`, `start.bat` (health waits), `stop.bat`, `test.ps1`; `test_stage10_release.py` checks they exist and never delete data | Scripts reviewed by hand; PowerShell wasn't available to run them | **Run `install.bat` and `start.bat`** |
| 2 | No fake data; empty states are real | `test_empty_day_is_all_zero_not_invented`; no seeded jobs; every report figure is a database count | ✅ | |
| 3 | Profile from your resume; skills verified only from the file | `test_stage4_profile_eligibility.py`; acceptance journey uploads a real PDF | ✅ | |
| 4 | Discovery from real sources, with duplicate and expiry detection and visible source health | `test_stage3_discovery.py` (mocked sources); live run here: 3 real listings from the SimplifyJobs feed (updated 2026-11-25), and the other sources were refused by the sandbox proxy and reported as failures | ✅ (Simplify) | **`.\test.ps1 -Live`** for Arbeitnow, Jobicy, Remotive, WWR, Adzuna and boards |
| 5 | Eligibility is PASS / FAIL / UNKNOWN with evidence; UNKNOWN never passes | `test_stage4_profile_eligibility.py`, `test_stage2_regressions.py` | ✅ | |
| 6 | Explainable match score and next action; ranked opportunities | `test_stage4…`, `test_stage8_frontend_api.py` | ✅ | |
| 7 | Drafts are grounded; flagged claims need acknowledgement before approval | `test_stage5_applications.py` | ✅ (template drafts) | **Live:** `test_cover_letter_with_real_model_is_grounded` |
| 8 | Default is PREPARE ONLY | `test_new_profile_defaults_to_prepare_only` | ✅ | |
| 9 | Nothing is submitted without your approval **and** a confirmation for that application | `test_full_journey` (409 before approval, 409 without confirmation, then a real confirmed submit), `test_stage2_regressions.py` | ✅ | |
| 10 | No duplicate applications; sent ones are frozen | `test_full_journey`, `test_stage5…` | ✅ | |
| 11 | CAPTCHA, login and anti-bot checks pause the run and are never bypassed | `test_phase6.py`, `test_stage6_browser.py` | ✅ | |
| 12 | Legal, demographic and sensitive questions are never auto-answered | `test_stage6_browser.py`; `test_full_journey` ("Gender" left for you) | ✅ | |
| 13 | Form filling on Greenhouse, Lever and Ashby; explained export for unsupported sites | `test_stage6_browser.py` on **reconstructed** ATS pages | ✅ (reconstructions) | **Preview a real posting** (`LIVE_ATS_URL=… pytest -m live`) before relying on Fill |
| 14 | Emergency Stop halts everything and survives a restart until Resume | `test_emergency_stop_halts_everything_until_resume` | ✅ | |
| 15 | Tracker: 14-stage lifecycle with history, notes and follow-ups | `test_stage5…`, `test_stage7_reporting.py` | ✅ | |
| 16 | Scheduler runs daily or at an interval, survives restart and pauses on halt | `test_stage7_reporting.py` | ✅ | Needs `tzdata` (installed by `install.bat`) |
| 17 | Daily reports are correct per local day | `test_stage7_reporting.py` (records either side of midnight) | ✅ | |
| 18 | Usable on iPhone (PWA over LAN) | 390×844 browser checks of all 9 pages; QR pairing through the real proxy | ✅ (emulated) | **Real iPhone:** scan, Add to Home Screen |
| 19 | Security: local bind, CORS/CSRF, phone access code, uploads, SSRF, headers, log masking | `test_stage2_regressions.py`, `test_stage9_security.py` | ✅ | |
| 20 | Your data is preserved: isolated tests, in-place migrations, backups and restore, no destructive scripts | `tests/_isolation.py`; old-schema upgrade test; `test_stage9_security.py` backups; the delete-everything `harvest_*` scripts were removed | ✅ | Run `backup.bat` once |
| 21 | No secrets or personal data in tracked files | `test_stage10_release.py`; hashed check for your phone and e-mail in `test_stage2_regressions.py` | ✅ | Older **Git history** still contains them; rewriting it is your decision |
| 22 | AI runs locally only (Ollama `qwen2.5:1.5b`) | Ollama is the only AI client (`ollama_service.py`) and there are no other AI endpoints | Code ✅ | **Live:** `test_ollama_running_with_model`, `test_ollama_generates_text` |

## Test results here (2026-11-26)

See the Stage 10 section of [PROGRESS.md](PROGRESS.md) for the exact counts from the final run.

## Steps for you on Windows

1. `install.bat`, then `start.bat`. Check that the app opens at http://localhost:5173.
2. `.\test.ps1 -Live`. Expect every suite to pass; send the output if not.
3. Resumes → upload your real resume; Profile → fix anything the profile-health card flags (for example a CGPA that differs from your resume).
4. Settings → follow 2–3 company boards → Dashboard → Run Discovery Now → Source Health.
5. Tracker → **Preview form** on one real Greenhouse/Lever/Ashby posting (nothing is typed).
6. iPhone: Settings → Phone access → scan → Add to Home Screen.
7. `backup.bat`.
