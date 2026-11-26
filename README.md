# Agent KitKat

A personal job-hunting assistant that runs on your own Windows computer. It finds internships and
entry-level tech jobs, checks whether you're actually eligible, scores how well each one fits your
resume, drafts the application, and can fill the form for you to check. **It never sends an
application unless you approve that application and then confirm it once more.** By default it
only prepares drafts and never sends anything.

* **Local and free:** a small local AI model (Ollama, `qwen2.5:1.5b`) and free public job sources.
  No paid APIs, no account, and your data stays on your computer (`storage\`).
* **Honest:** every number comes from your database. Eligibility is `PASS`, `FAIL` or `UNKNOWN`
  (unknown never counts as a pass). Drafts are checked against your resume, and unsupported
  claims are flagged before you can approve.
* **Use it from your iPhone** over your Wi-Fi, paired with a QR code.

Version **1.0.0-rc.1**. What is verified, and where, is in [FEATURE_STATUS.md](FEATURE_STATUS.md)
and [ACCEPTANCE.md](ACCEPTANCE.md). Day-by-day changes are in [PROGRESS.md](PROGRESS.md) and
[CHANGELOG.md](CHANGELOG.md).

---

## Install (once)

You need:
* **Python 3.11 or newer**: https://www.python.org/downloads/windows/ (tick *Add python.exe to PATH*)
* **Node.js LTS** (20.19+ or 22.12+): https://nodejs.org/
* Optional but recommended: **Ollama** (https://ollama.com/download/windows). Without it,
  cover letters and answers use simple templates instead of the AI.

Then double-click **`install.bat`**. It:
1. checks Python and Node,
2. creates `venv\` and installs the exact tested package versions (`backend\requirements.lock.txt`),
3. installs the Chromium browser used for filling forms,
4. installs and builds the frontend,
5. creates `.env` from `.env.example` (never overwrites yours),
6. checks Ollama and offers to download the model (about 1 GB),
7. runs a quick self-test on a temporary database.

It is safe to run again (for example after `git pull`).

## Start, stop, back up

| | |
|---|---|
| **Start** | `start.bat`: starts the backend and frontend, waits until both answer, then opens http://localhost:5173 |
| **Stop** | `stop.bat` |
| **Back up** | `backup.bat`. One backup is also made automatically each day (the last 7 are kept) in `storage\backups\` |
| **Restore** | `stop.bat`, then `restore.bat`. It checks the backup and saves your current data first |
| **Logs** | `storage\logs\agent_kitkat.log` (personal details are masked) |

## First steps in the app

1. **Resumes:** upload your resume (PDF or DOCX). Skills count as *verified* only if they are
   actually in the file.
2. **Profile:** fill in education (degree, graduation year, CGPA), preferred roles and locations.
   The profile-health card points out gaps and mismatches with your resume.
3. **Settings:**
   * **Discovery schedule:** once a day, or every few hours.
   * **Company career boards:** paste Greenhouse / Lever / Ashby careers URLs of companies you like.
     This is the best source of India roles.
   * **Submission policy:** *Prepare only* (default) or *Approve, then confirm*.
4. **Dashboard → Run Discovery Now**, then open **Opportunities**.

## How it works

```
Discovery ─► Eligibility ─► Match score ─► Draft ─► Your review ─► (optional) fill form ─► you submit
 sources      PASS/FAIL/      explainable     cover    edit, approve       screenshot of      or confirm
 + boards     UNKNOWN         0-100           letter   or reject           the filled form    one send
```

* **Discovery** (`Dashboard`, schedule, or `python scripts\run_discovery.py`): SimplifyJobs
  internship and new-grad lists, Arbeitnow, Jobicy, Remotive, We Work Remotely, Adzuna India
  (optional free key), and the company career boards you follow.
  * Duplicates are detected by link and by company/title/location.
  * Listings a source takes down are marked expired.
  * The **Source Health** panel shows what each source returned and any errors.
* **Eligibility:** 10 checks: degree, graduation year, CGPA, backlogs, experience level,
  location (country-restricted "remote" counts), work mode, work authorisation, required skills,
  and other stated conditions. Each check shows its
  evidence and whether the posting stated it or it was inferred.
* **Match score:** skills 35, education 20, projects 20, role relevance 15, location 10.
  * Factors that can't be judged are left out and the rest are rescaled.
  * Every job gets a suggested next action.
* **Opportunities:** eligible jobs first, then needs-checking, then not evaluated, then not
  eligible; best score first within each group. Filters, search and pages. From here you can
  **Shortlist** or **Prepare**.
* **Approvals:**
  * Edit the draft; every version is kept and can be restored.
  * A grounding check flags skills, numbers, employers or CGPA that your resume doesn't support.
  * Approving needs you to acknowledge any flags.
* **Tracker:** 14 stages (Discovered → … → Submitted → Assessment → Interview → Offer /
  Rejected), with history, notes, follow-up dates and confirmation IDs.
  * **Preview form** shows what would be filled for each field, without typing anything.
  * **Copy prepared application** gives you everything to paste on sites that can't be automated.
* **Form filling** (Greenhouse, Lever, Ashby; other sites best-effort):
  * Fields are matched by their visible labels.
  * Demographic, visa/sponsorship, work-authorisation, date-of-birth, consent and background-check
    questions are **never answered for you**.
  * CAPTCHAs and logins **pause** the run; they are never bypassed.
  * LinkedIn, Naukri, Indeed, Internshala, Workday and similar sites are not automated. You get a
    ready-to-paste export instead.
* **Daily reports:** what happened each day in your timezone (`TIMEZONE`, default Asia/Kolkata).
  Includes follow-ups due and source errors.
* **Emergency Stop** (top bar):
  * Closes any automation browser, stops discovery and pauses the schedule.
  * It stays stopped, even after a restart, until you press **Resume**.

## Your phone

Settings → **Phone access**: scan the QR code with your iPhone camera, open it in Safari, then
*Share → Add to Home Screen*.
* Other devices on your Wi-Fi need this access code.
* You can make a new code (this unpairs every phone) or turn phone access off.
* Setup details, firewall tips and optional HTTPS: [docs/IPHONE.md](docs/IPHONE.md).

## Settings file (`.env`)

| Key | Default | Meaning |
|---|---|---|
| `TIMEZONE` | `Asia/Kolkata` | Day boundaries for reports and the daily schedule |
| `OLLAMA_MODEL` | `qwen2.5:1.5b` | Local model (`ollama pull <name>`) |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | `120` | CPU-only machines can be slow |
| `HTTP_TRUST_ENV` | `False` | `True` if your network needs a system proxy |
| `CORS_EXTRA_ORIGINS` | empty | Extra phone addresses outside home ranges (e.g. a VPN) |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | empty | Optional free Adzuna India keys |
| `SIMPLIFY_INTERNSHIPS_URL`, `SIMPLIFY_NEW_GRAD_URL` | current lists | Override if a feed moves |
| `MAX_UPLOAD_MB` | `10` | Resume / job-file upload limit |

Your profile is entered in the app. To pre-fill a **new** profile, copy `profile_seed.example.json` to
`profile_seed.json`; that file is git-ignored.

## Tests

```powershell
.\test.ps1            # pytest (all stages) + legacy phase scripts + frontend build
.\test.ps1 -Live      # also real Ollama and real job sites (pytest -m live)
.\test.ps1 -Quick     # pytest only
```
All tests use a temporary database and storage folder; your data is never touched.
The `-Live` checks are the ones that couldn't be run in the development sandbox (see
[ACCEPTANCE.md](ACCEPTANCE.md)). Please run them once on your computer.

## Project layout

```
backend/
  main.py               FastAPI app, security middleware, serves the built UI at /ui
  config.py             settings (.env)
  logging_setup.py      rotating JSON log, personal-data masking
  database/             SQLite models, automatic migrations
  agents/               eligibility, matching, grounding, application drafting, form mapping, browser
  services/             discovery, applications + lifecycle, reports, halt, phone access, ...
  routers/              REST API (see http://127.0.0.1:8000/docs on this computer)
  tools/                job sources, company boards, safe HTTP fetch, duplicate checks
  scheduler/            daily / interval discovery schedule
  maintenance/backup.py backup / verify / restore
frontend/               React 19 + Vite + Tailwind (PWA)
scripts/                run_discovery.py, db_summary.py (read-only), import_resume.py
tests/                  test_stage2..10 (pytest), legacy test_phase*.py
docs/IPHONE.md          phone setup
install.bat / start.bat / stop.bat / backup.bat / restore.bat / test.ps1
```

## Rules this project keeps

1. **No fake data.** Nothing is invented: no sample jobs, no made-up numbers, and no skills that
   aren't in your resume.
2. **You decide.** Prepare-only by default. Sending needs your approval *and* a final confirmation
   for that one application, and it is never automatic.
3. **No bypassing.** CAPTCHAs, logins and anti-bot checks pause the run for you.
4. **Sensitive questions are yours.** Legal, demographic and consent questions are never answered
   automatically.
5. **One application per job.** Sent applications are frozen.
6. **Your data stays yours.** It is local, git-ignored and backed up daily. Other devices need your
   access code, and personal details are masked in logs.
