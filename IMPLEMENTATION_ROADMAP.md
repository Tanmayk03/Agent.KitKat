# Implementation Roadmap

Ordered by risk first, then value. Every stage ends with: tests run and results recorded in `PROGRESS.md`, `FEATURE_STATUS.md` updated, and a checkpoint commit. Finding IDs (C1, H3, …) refer to `AUDIT_REPORT.md`.

## Stage 1: Audit ✅
`AUDIT_REPORT.md`, `FEATURE_STATUS.md`, this file.

## Stage 2: Critical fixes and safe testing ✅ (this branch)
* C4: test isolation (temp DB and storage), plus a pytest regression suite (`tests/test_stage2_regressions.py`).
* C1, C2, C3, M5, M6: browser approval gate, no auto-answers, truthful confirmation, no evasion flag, duplicate guard.
* C5: CORS allow-list and origin check on writes; bind to 127.0.0.1 by default.
* C6, H4: dedupe scoped by source with `.first()`; per-item error isolation; fabricated fields removed; `source_results`.
* H1, H2: frontend API contracts. Approve now *prepares* (fills the form and takes a screenshot); final submit is a separate confirmed action.
* H3, H5, H6, H7, H8: unknown batch → UNKNOWN, extraction regexes, skill regexes, grounded answers, no overwriting submitted applications.
* H9: scheduler persisted, starts at boot, overlap lock.
* C7: personal data removed from code.
* M1, M2: upload sanitisation, SSRF guard.
* Old test scripts brought in line with corrected behaviour where they encoded drift.

## Stage 3: Job discovery and source reliability ✅ (see PROGRESS.md for what shipped and its limits)
* `SourceRun` table: source, started/finished, fetched, new, duplicates, expired, error, HTTP status.
* Shared `fetch_json()`: timeout, 3 retries with exponential backoff and jitter, honours 429 `Retry-After`, respects `HTTP(S)_PROXY` (configurable `trust_env`).
* Pagination where the API supports it (Remotive has none; Arbeitnow `?page=`; Jobicy `count`; Simplify is one file).
* Store `posted_at`, `fetched_at`, `last_seen_at`, `employment_type`, `source_url`. Mark `expired` when an active-flag feed drops a listing or `active:false`.
* `dedupe_key` column (source + external id, else normalised company + title + location) with a unique index.
* Configurable feed URLs (Simplify season repo). Evaluate an India-centric free source (e.g. official career pages with public JSON such as Greenhouse/Lever boards for a user-maintained company list).
* Dashboard **Source Health** panel. Run discovery as a background task with polled progress.
* Tests: fixture payloads per connector, failure/timeout/429, dedupe across sources, expiry. Live smoke test runs separately and is marked BLOCKED when offline.

## Stage 4: Profile, resume, eligibility, matching ✅
* Profile validation and missing-info warnings (CGPA, backlogs, grad year, phone, links); `active_backlogs` field; work-authorisation field.
* Resume → profile import with review (diff: accept/reject per field); multiple resumes, one active.
* `JobRequirements` Pydantic schema where each field is `{value, provenance: explicit|inferred|missing, evidence: "quoted text"}`. LLM output validated against it, with values that cannot be found in the text dropped.
* Eligibility over 10 dimensions with evidence snippets; UNKNOWN → "Confirm" action in the UI.
* Matching: remove arbitrary baselines (no listed skills → factor marked N/A and weights renormalised and shown); project relevance by skill overlap with each project's stack; next-action recommendation.

## Stage 5: Application preparation and tracking
* `DraftVersion` table; edits create versions; diff view.
* Grounding checker: every claim in a generated letter must map to a profile or resume fact; flag unsupported sentences.
* 14-status lifecycle as an enum with allowed transitions; `ApplicationEvent` history; notes, follow-up dates, confirmation ID, evidence paths.
* Tracker: search, filter, sort, pagination, status updates.

## Stage 6: Playwright automation and human approval
* Field detection by label text (aria/label/for) instead of name substrings; a field map preview before filling.
* Adapters for Greenhouse, Lever and Ashby public forms; unsupported-site explanation and a prepared-application export.
* Save form state (JSON) and step screenshots; review screen shows exactly what will be sent.
* Sensitive question classifier (demographics, legal, background-check) → always manual.
* Global "halt" flag from emergency stop that also pauses the scheduler until reset.

## Stage 7: Scheduler and reporting
* Interval or cron options; run history table; failure log; daily summary generation.
* Reports computed per day (jobs created that day, evaluations that day, applications by status-change date). GET is read-only; POST generates.

## Stage 8: Frontend and mobile
* Opportunities page from rankings (score, eligibility, reasons, next action); shortlist button; pagination.
* Toast notifications instead of `alert()`; consistent loading, empty and error states.
* PWA: network-first HTML, PNG icons, `apple-touch-icon`; documented HTTPS option (`mkcert`) for a real service worker on iPhone.

## Stage 9: Security and reliability
* Optional LAN access token (generated on first LAN start, shown as a QR code in Settings, sent as a header).
* Mask PII in browser logs; SQLite WAL; structured log file rotation; backup and restore scripts.

## Stage 10: Integration and release
* `install.ps1` (venv, pip, npm, Playwright browser, Ollama model check), `start_all.ps1` health wait, `test.ps1`.
* End-to-end acceptance run against the 20 criteria; README rewritten to match reality.

## Known blockers
* **Ollama** and **live job APIs** could not be reached from the audit sandbox; those checks must be run on your Windows machine (`pytest -m live`).
* **Git history** contains your phone and email; rewriting public history is your decision.
* **Push access**: this session had read-only access to GitHub, so changes are delivered as a branch bundle and patch.
