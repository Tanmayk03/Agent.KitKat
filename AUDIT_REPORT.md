# Agent KitKat — Repository Audit Report

**Audit date:** 2026-11-25 · **Commit audited:** `e279348` (main)

The audit covered every file: backend config, DB, models, all 9 routers, all services and agents, tools, the scheduler, all 9 frontend pages, the API client, the PWA files, PowerShell scripts and all 11 test scripts.

I did not take README or PROGRESS.md claims on trust. Every claim below was checked by reading the code, by **running it**, or by both. Commands ran on Linux, Python 3.13, Node 22, in a throwaway copy of the repo.

Some things could not be reached from the audit sandbox: Ollama, and the outbound job APIs (DNS was blocked). Those items are marked **BLOCKED**, not passed.

---

## 1. Executive summary

The project has a good skeleton. The FastAPI app boots, the SQLite schema is created, the React app builds, and the Playwright agent can fill a simple HTML form. Most of the **domain logic is in place, but it is either unsafe or quietly wrong**:

* **The approval gate can be bypassed.** `POST /api/browser/run/{id}` with `auto_submit=true` submits a draft that was never approved. *(Reproduced.)*
* **Browser automation makes things up.** It ticks the first "Yes" radio on the page (a disability question in my probe). It pastes the cover letter into any textarea. It then reports **"Submission CONFIRMED"** on a page that never submitted, because "thanks for your interest" was already on the page. *(Reproduced.)*
* **The test suite deletes your real data.** The tests run against `storage/agent_kitkat.db` and execute `DELETE FROM jobs/resumes/...`. Running `run_all_tests.ps1` wipes your jobs, resumes and drafts.
* **Any website you visit can drive the API.** CORS reflects *any* origin with credentials, and the backend binds to `0.0.0.0` with no authentication. *(Reproduced: `Origin: http://evil.example` was echoed back.)*
* **The "Approve" button and the "Analyse text" feature are broken in the UI.** The frontend sends `{decision, notes}` and `{raw_text}`; the backend expects `{action, decision_notes}` and `{text}`. Both return HTTP 422. *(Reproduced.)*
* **Discovery makes up data.** Salary strings such as "Paid Internship / Stipend", "Competitive Remote Rate" and "Disclosed upon application" are invented. So are company fallbacks ("Tech Company"), work modes ("Hybrid" for any India listing) and index-based external IDs. If one source returns two jobs with external id `"0"`, the duplicate checker raises `MultipleResultsFound`, which aborts the whole discovery run. *(Reproduced.)*
* **Eligibility treats unknowns as PASS.** A missing graduation batch is reported as PASS. The repo's own `test_phase4.py` expects UNKNOWN and **fails**.
* **"Verified" skills are inflated by loose regexes.** For example, `CV` → Computer Vision, `express interest` → Express.js, and `Section C` → C. *(Reproduced.)*
* **Generated application answers make claims that may be false.** One answer says "I built autonomous and web development projects using Python, React, and SQL" whatever the profile contains. Others say "Available immediately" and "Authorized to work in India / no sponsorship", and are auto-filled.
* **Personal data is in public source code.** Your phone number and email are hard-coded in `profile_service.py` and `scripts/import_tanmay_resume.py`, and are in Git history.
* `scripts/import_tanmay_resume.py` **generates a synthetic PDF** from hard-coded text and registers it as your resume. Skills "verified" against it are verified against text the tool wrote itself.
* **README and PROGRESS claim 10/10 suites "100% PASS".** When I ran them, **7 of 11 failed**. 2 failures are environmental (Ollama, network). The other 5 are genuine drift or genuine bugs (§6).

**Evidence-based completion: ~38%** (method in §7).

---

## 2. Architecture assessment

| Layer | Assessment |
|---|---|
| **Backend structure** | Clean layering (router → service → agent/tool → model). Async SQLAlchemy is used correctly for the most part. `backend/` and `backend/scheduler/` have no `__init__.py`, so they rely on namespace packages. This works, but it is fragile. |
| **Persistence** | `create_all` plus a list of `ALTER TABLE` statements with `except: pass`. There is no migration history or versioning. One-to-one tables (`EligibilityResult`, `MatchResult`, `ApplicationDraft`) are keyed by `job_id` with no unique constraint. `experience_level` is computed but **not persisted**, so it is lost on re-read. |
| **Statuses** | There is no single state machine. Application statuses are free strings across 4 tables (`draft`, `approved_for_submission`, `filled_ready_for_review`, `submission_uncertain`, `auto_approved`, …). The 14 lifecycle statuses in the spec do not exist. |
| **Config** | `pydantic-settings` is good. DB and storage paths are relative to the CWD, so starting from another folder creates a new empty DB. |
| **AI layer** | Ollama client wrapper is fine. LLM output is parsed with a regex `{...}` and **not validated against a schema**. The extraction prompt contains concrete example values (`7.5`, `[2026, 2027]`, `"₹25,000/month"`, `"Bangalore"`), which a 1.5B model often copies verbatim into its output. |
| **Long-running work** | Discovery, "scheduler trigger" and browser runs all execute **inside the HTTP request**. There are no background jobs, progress reporting or cancellation, apart from the browser kill switch. |
| **Frontend** | One `App.jsx` state container plus 9 pages, with no router. It builds cleanly (Vite 8, React 19, Tailwind 4). Data is real API data, with no mock arrays. Two API contract mismatches. Uses `alert()` for errors. The Opportunities page shows `/api/jobs`, which has no score or eligibility. |
| **Duplication** | Location, seniority and intern regex lists are copied in 3 files (`job_discovery_sources.py`, `eligibility_agent.py`, `job_reader.py`). |

Verdict: **keep the architecture.** Nothing here justifies a rewrite. The work is to correct and harden it.

---

## 3. Findings

Severity scale: **Critical** means data loss, an unsafe action or a security hole. **High** means a core feature is wrong or broken. **Medium** means it works but is unreliable or misleading. **Low** means polish or debt.

### 3.1 Critical

| # | Feature | Problem (evidence) | Files | Required fix | Verification |
|---|---|---|---|---|---|
| C1 | Approval gate | `auto_submit=true` submits **any** draft, approved or not. Probe: a `pending_approval` draft gave result `submitted`. The "Approve" button also auto-submits immediately, with no review of the filled form. | `services/browser_service.py`, `agents/browser_agent.py`, `pages/ApprovalsPage.jsx` | Server-side guard: submit only when the draft is `approved` **and** the request carries an explicit per-application confirmation. Approving should run *prepare-only* (fill plus screenshot). Final submit is a separate, confirmed action. | Regression test: a pending draft with `auto_submit` returns 409. |
| C2 | Fabricated form answers | Any page with a radio named `*authoriz*`/`*eligible*` causes the **first** `value*=yes` radio anywhere on the page to be checked. In the probe that was the *disability* question. Sponsorship is auto-set to "No". The cover letter falls back to the **first textarea** on the page. | `agents/browser_agent.py` (`_fill_form_fields`) | Remove the auto-answers for authorisation, sponsorship and demographics. Remove the generic textarea fallback. Report these fields as unsupported questions. | Probe page: the disability radio stays unchecked; the field is listed as needing input. |
| C3 | False submission confirmation | The confirmation check searches the *raw HTML* for phrases such as "thanks for your interest". Many forms show that before submission. Probe: a form with `onsubmit="return false"` was reported as **CONFIRMED**. | `agents/browser_agent.py` (`_verify_submission_confirmation`) | Compare visible text before and after the click. Require a new confirmation phrase or a navigation. Otherwise mark `submission_unverified`. | Probe page returns `submission_unverified`. |
| C4 | Tests destroy real data | Every test imports the production `AsyncSessionLocal` (`storage/agent_kitkat.db`) and runs `delete(Job)`, `delete(Resume)`, … | `tests/*.py`, `run_all_tests.ps1` | Point tests at a temp DB and temp storage through env vars **before** importing `backend`. Add a guard that refuses destructive test setup on the real DB. | Run the suite and confirm the checksum of the real DB is unchanged. |
| C5 | Open API (CORS / CSRF / LAN) | `allow_origins=[…,"*"]` with `allow_credentials=True`, so Starlette echoes any `Origin`. The backend binds to `0.0.0.0` with no auth. Any web page you visit (or anyone on the Wi-Fi) can read your profile, upload files, start discovery or start browser submissions. | `backend/main.py`, `start_backend.ps1` | Use an explicit origin allow-list (localhost and private LAN only). Add origin checks on state-changing requests. Default bind `127.0.0.1`. Add an optional LAN access token. | `curl -H "Origin: http://evil.example"` gets no ACAO header and a 403 on POST. |
| C6 | Discovery crash | External IDs are not scoped by source, and fall back to list indexes (`"0"`, `"1"`). `scalar_one_or_none()` then raises `MultipleResultsFound`, which is not caught, so the run aborts. *(Reproduced.)* | `tools/duplicate_checker.py`, `tools/job_discovery_sources.py`, `services/discovery_service.py` | Scope dedupe by `(source, external_id)`, use `.first()`, catch errors per item. | Unit test with two rows sharing an id. |
| C7 | Personal data in source code | Phone and email are hard-coded in `profile_service.py` and the import script, and are in public Git history. | `services/profile_service.py`, `scripts/import_tanmay_resume.py` | Seed the profile from a gitignored local file or the UI, never from code. **You** decide whether to rewrite Git history or rotate the number and email. | `grep` finds no PII in tracked files. |

### 3.2 High

| # | Feature | Problem | Files | Fix | Verify |
|---|---|---|---|---|---|
| H1 | Approvals UI | `decideApproval` sends `{decision:"approved", notes}`; the API needs `{action:"approve", decision_notes}`, so it returns **422** *(reproduced)*. Even with the keys fixed, `"approved" != "approve"` means everything would be **rejected**. | `frontend/src/services/api.js`, `backend/schemas/application.py` | Fix the payload. Use `Literal["approve","reject"]` on the server. | API test plus manual UI check. |
| H2 | Analyse-text UI | Sends `raw_text`; the API needs `text`, so it returns **422** *(reproduced)*. Mode B "paste JD" is dead in the UI. | `api.js` | Send `text`. | API contract test. |
| H3 | Eligibility unknowns | A missing graduation batch is reported as PASS. `test_phase4` itself expects UNKNOWN and fails. Work mode passes if the word "remote" appears anywhere in the JD. Candidate CGPA and grad year fall back to hard-coded `8.44`/`2027` when the profile is empty. | `agents/eligibility_agent.py` | Missing batch → UNKNOWN with reason "not stated". Missing profile data → UNKNOWN. Work mode from structured fields only. | `test_phase4` Test 4 passes; new unit tests. |
| H4 | Fabricated job data | Invented salary strings, `"Tech Company"`/`"Tech Startup"` company names, India → `"Hybrid"`, unknown experience → `"Fresher / Intern"`. Posted date is never stored. | `tools/job_discovery_sources.py`, `agents/job_reader.py`, `services/discovery_service.py` | Use `None`/UNKNOWN when absent. Skip listings with no company. Store `posted_at` and `fetched_at`. | Connector unit tests with fixture payloads. |
| H5 | JD extraction errors | `\bb\.?e\b` matches the word **"be"**, so almost every English JD "requires B.Tech". Seniority is detected anywhere in the body ("work with senior engineers" → Senior). The LLM prompt's example values get copied. | `agents/job_reader.py` | Tighten the regexes. Detect seniority in the title only. Use placeholder schema text. Accept LLM CGPA/batch values only if they appear in the source text. Validate with Pydantic. | Unit tests with tricky JDs. |
| H6 | Skill inflation | `\bcv\b`, `\bc\b`, `\bgo\b`, `\bexpress\b`, `\brest\b`, `\bnode\b`, `\bts\b`, `\btf\b`, `\bdl\b` all produce false positives *(reproduced)*. Every "verified skill" and every "required skill" is affected. | `tools/resume_parser.py` | Drop or contextualise the ambiguous patterns. | Unit test with the probe sentence. |
| H7 | Fabricated application answers | `relevant_project` claims projects that may not exist. `availability` says "Available immediately". Work authorisation and sponsorship are hard-coded. The fallback cover letter says "I have built robust projects". The default skills are "Python, Web Development". | `agents/application_agent.py` | Ground answers only in profile and resume. Otherwise mark the field `NEEDS_YOUR_INPUT`. | Grounding unit test. |
| H8 | Re-prepare overwrites history | `prepare_application` overwrites an existing draft and resets it to `pending_approval`, even after submission. There is no versioning. | `services/application_service.py` | Refuse to re-prepare a submitted application. Keep draft versions (Stage 5). | Unit test. |
| H9 | Scheduler | Not started at boot and not persisted, so after a restart nothing runs. There is no overlap lock (`trigger` plus cron can run concurrently). `trigger` blocks the HTTP request for the whole run. | `scheduler/daily_scheduler.py`, `main.py` | Persist the setting, start it in the lifespan, use `max_instances=1` and an asyncio lock, return 409 when busy. | Unit test. |
| H10 | Source health invisible | When all sources fail, discovery returns `200 {"total_discovered":0}` and the errors are only logged *(reproduced)*. There is no retry, backoff, pagination or rate-limit handling. | `tools/job_discovery_sources.py`, `services/discovery_service.py` | Per-source results (fetched, errors, duration), persisted `SourceRun` rows, dashboard panel. | Mocked failure test. |
| H11 | Synthetic "real" resume | `import_tanmay_resume.py` writes a PDF from hard-coded text and registers it as your resume. | `scripts/import_tanmay_resume.py` | Remove from the normal workflow. Profile comes from your uploaded resume only. | Doc plus review. |

### 3.3 Medium

| # | Problem | Files | Fix |
|---|---|---|---|
| M1 | Upload path traversal on Windows. The filename is used raw (`uuid_..\..\..\x.pdf` normalises to outside `storage/resumes`; verified with `ntpath`). There is no size limit, and the file stays on disk if parsing fails. Same issue for JD uploads. | `services/resume_service.py`, `services/job_service.py` | Sanitise to basename plus safe characters, cap at 10 MB, clean up on error. |
| M2 | SSRF: Mode B URL fetch follows redirects to any host, including `127.0.0.1:11434` and LAN devices. | `tools/url_reader.py` | Block private, loopback and link-local targets. |
| M3 | URL normalisation strips **all** query params, so `?id=1` and `?id=2` collide *(reproduced)*. Dedupe loads the whole `jobs` table once per item (O(n²)). | `tools/duplicate_checker.py` | Strip tracking params only. Add a `dedupe_key` column with an index. |
| M4 | Daily report numbers are **cumulative totals** shown under "Report Date". `GET /api/reports/daily` writes to the DB, and the dashboard calls it on every load. Shortlist threshold is hard-coded at 75. | `services/reporting_service.py` | Per-day queries. Separate GET (read) from POST (generate). |
| M5 | Playwright launched with `--disable-blink-features=AutomationControlled`, which is an anti-bot evasion flag and contradicts the no-bypass policy. | `agents/browser_agent.py` | Remove. |
| M6 | No duplicate-submission guard. A submitted application can be run again with `auto_submit`. | `services/browser_service.py` | Refuse when the status is already submitted or confirmed. |
| M7 | Simplify feed URL is the season-named `Summer2025-Internships` repo, and the feed is US-centric (few India roles). Needs checking each season. | `tools/job_discovery_sources.py` | Make the URL configurable. Record feed staleness. |
| M8 | Service worker is cache-first for `/` and `index.html`, so the app can stay stale after updates. Service workers **do not run over `http://<LAN-IP>`** (not a secure context), so the "offline PWA on iPhone" claim is false. The manifest has SVG icons only, which iOS ignores. | `frontend/public/sw.js`, `manifest.json` | Network-first for HTML. Add PNG `apple-touch-icon`. Document HTTPS limits honestly. |
| M9 | Three defaults disagree: README says the profile is "Harshit Sharma", `ProfilePage.jsx` defaults CGPA 8.53, the backend uses 8.53/8.44. | several | Single source of truth: your profile record. |
| M10 | `trust_env=False` on every HTTP client ignores system proxies (corporate or college networks). | tools/services | Make it configurable. |
| M11 | Errors swallowed: `except Exception: pass` in migrations, the form filler and source fetchers. | many | Log and surface. |

### 3.4 Low / technical debt
* Regex lists are duplicated in 3 modules. Free-string statuses. No unique constraints. `datetime.utcnow()` (deprecated). Singleton services instantiated with static methods.
* `start_all_backup.ps1` is a stale duplicate. `requirements.txt` is unpinned (Playwright ≥1.40 needs a matching browser build; tests broke on 1.65 vs an installed 1.63 browser).
* `alert()`-based UI errors. No pagination on lists. Opportunities page cannot show match or eligibility.
* README architecture table lists a "Curated Tech Feed" that no longer exists, which is why `test_phase7` fails.

---

## 4. Security findings (summary)

| Area | Status |
|---|---|
| Secrets / env | No API secrets in the repo. **Personal data is in code** (C7). `.env` is correctly gitignored. |
| CORS / CSRF / LAN exposure | **Critical** (C5). |
| File uploads | Path traversal (Windows), no size cap (M1). Extension-only type check. |
| Resume storage | Stored unencrypted under `storage/resumes`, gitignored, which is acceptable for a single-user local app. Screenshots can contain PII and are served without auth (C5). |
| Path traversal (screenshots) | `basename()` used, OK. |
| SQL injection | None found. All queries go through the ORM or bound parameters. |
| XSS | React escapes by default. No `dangerouslySetInnerHTML` found. |
| SSRF | Mode B URL fetch (M2). |
| Browser session isolation | A fresh context per run with no persisted cookies. Good. Evasion flag (M5). |
| Logging of sensitive data | Browser logs record filled values, such as `Filled field 'phone' -> +91…`, and these are stored in the DB and returned by the API. Should be masked. |
| DB concurrency | SQLite with async sessions. Long-running requests hold sessions. No WAL. Acceptable at single-user scale; enable WAL. |

## 5. Performance and memory
* Dedupe and reports load entire tables into Python per call (O(n²) during discovery).
* Ollama is called once per prepared draft inside the request, at about 30–120 s on CPU with 8 GB RAM. Discovery with auto-prepare can therefore run for many minutes in one HTTP request.
* Each browser run launches a fresh Chromium, which is fine. There is no concurrency limit (two parallel runs means about 2× 300 MB).

## 6. Test coverage assessment (executed, not claimed)

| Suite | What it actually checks | Result here | Cause |
|---|---|---|---|
| test_phase1 | Health shows Ollama healthy | **BLOCKED** | Needs a live Ollama |
| test_live_server | Same, over a socket | **BLOCKED** | Ollama |
| test_phase2 | Profile and resume CRUD | **FAIL** | Test expects old specialisation string (drift) |
| test_phase3 | Mode B analysis | PASS | Works without Ollama through the fallback |
| test_phase4 | Eligibility and matching | **FAIL** | **Real bug H3**: missing batch returns PASS |
| test_phase5 | Drafts and policies | PASS | |
| test_phase6 | Playwright fill, CAPTCHA, login, declaration | PASS* | *After pinning Playwright to the installed browser. Seeds drafts as `approved`, so it never tests C1. |
| test_phase7 | Discovery and scheduler | **FAIL** | Expects removed `curated_feed` source |
| test_phase8 | Frontend | **FAIL** → PASS after `npm run build` | Only checks that files exist and method *names* are present. Does not catch H1/H2. |
| test_phase9 | PWA files | PASS | File existence only |
| test_master_e2e | Live discovery returns >0 | **BLOCKED** | Network |

Gaps: no pytest structure, no mocks for HTTP sources or Ollama, no contract tests between `api.js` and the backend, no safety tests for the approval gate, and no unit tests for regex extractors.

## 7. Completion percentage (method)

Each feature area was weighted by importance to the spec and scored on **demonstrated, correct behaviour**. A file or endpoint existing earns nothing on its own.

| Area | Weight | Score | Points |
|---|---:|---:|---:|
| Startup / config / DB | 5 | 80% | 4.0 |
| Ollama integration | 5 | 80% | 4.0 |
| Profile management | 8 | 45% | 3.6 |
| Resume upload and parse | 7 | 50% | 3.5 |
| Job discovery engine | 14 | 25% | 3.5 |
| Job analysis (Mode B) | 8 | 35% | 2.8 |
| Eligibility engine | 8 | 40% | 3.2 |
| Matching engine | 6 | 50% | 3.0 |
| Application preparation | 8 | 30% | 2.4 |
| Browser automation | 10 | 30% | 3.0 |
| Approvals and tracking | 7 | 20% | 1.4 |
| Scheduler | 5 | 30% | 1.5 |
| Daily reports | 3 | 40% | 1.2 |
| Frontend | 8 | 45% | 3.6 |
| PWA / mobile | 3 | 30% | 0.9 |
| Security | 5 | 10% | 0.5 |
| Tests | 5 | 20% | 1.0 |
| Install / docs | 5 | 40% | 2.0 |
| **Total** | **120** | | **45.1 → ≈ 38%** |

## 8. First five things to fix, and why

1. **`backend/agents/browser_agent.py` + `backend/services/browser_service.py`** (C1, C2, C3, M5, M6). This is the only code that can do irreversible harm in the real world: submitting unapproved, false or duplicate applications.
2. **`tests/` isolation** (C4). Until this is fixed, running the tests deletes your data. Every later stage depends on running tests safely.
3. **`backend/main.py` CORS and origin guard + `start_backend.ps1` bind** (C5). Closes drive-by control of the agent from any website.
4. **`backend/tools/duplicate_checker.py` + `job_discovery_sources.py` + `discovery_service.py`** (C6, H4, H10). Discovery is the core value. It currently crashes, makes up fields and hides failures.
5. **`frontend/src/services/api.js` + `ApprovalsPage.jsx`** (H1, H2). The two primary human-in-the-loop actions (analyse a JD, approve an application) do not work from the UI.

Then: eligibility unknowns (H3), extraction and skill regexes (H5, H6), grounded answers (H7), and personal data in code (C7).
