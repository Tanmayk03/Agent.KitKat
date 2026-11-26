# Feature Status — evidence-based

Legend: ✅ Working (demonstrated) · 🟡 Partial · 🧩 UI/placeholder only · ❌ Broken · ⬜ Missing · ⛔ Blocked (could not be verified in the audit environment)

Last updated: 2026-11-26, after Stage 9 (security and reliability). Rows changed in Stages 3–9 are marked (S3)…(S9). The "After Stage 2" column shows what changed. Details are in `PROGRESS.md`.

| Area | Feature | Before (audit) | After Stage 2 | Evidence / remaining gap |
|---|---|---|---|---|
| Platform | Backend boots, DB tables created | ✅ | ✅ | uvicorn boot plus 7 endpoints returned 200 |
| Platform | Frontend production build | ✅ | ✅ | `npm run build` OK |
| Platform | Tests isolated from the real DB | ❌ (tests wipe data) | ✅ | `tests/_isolation.py` sets the temp DB and storage before importing backend; `pytest` refuses the real DB |
| Platform | One-command install / test | 🟡 | 🟡 | `run_all_tests.ps1` now runs pytest; installer still to do (Stage 10) |
| Security | CORS / cross-site requests | ❌ (any origin) | ✅ | Allow-list of localhost and private-LAN origins; cross-site writes get 403 (test) |
| Security | LAN exposure / auth | ❌ | ✅ | Backend binds 127.0.0.1. Other devices need the phone access token (QR pairing, HttpOnly cookie, rotate, off switch); Host check blocks DNS rebinding (S9). Tests plus an end-to-end run through the real Vite proxy |
| Security | Security headers: CSP on the UI, nosniff, frame-deny, no-referrer, no-store on the API (S9) | ⬜ | ✅ | Tests |
| Security | Personal data masked in logs and stored browser logs; old rows scrubbed at startup (S9) | ❌ | ✅ | Tests (e-mail, phone, token; dates and IDs kept) |
| Reliability | JSON log file with rotation (5 MB × 5) (S9) | ⬜ | ✅ | Test plus e2e log check |
| Reliability | SQLite WAL + busy_timeout 5 s (S9) | 🟡 | ✅ | Test |
| Reliability | Backups: daily automatic (keep 7), manual, checksummed, verified; restore with safety backup and running check; backup.bat / restore.bat (S9) | ⬜ | ✅ | Tests plus a CLI run against a running and then stopped backend |
| Security | Upload sanitisation / size cap | ❌ | ✅ | Basename plus safe characters, 10 MB cap, cleanup on failure (tests) |
| Security | SSRF on URL analysis | ❌ | ✅ | Private, loopback and link-local hosts blocked (test) |
| Security | Personal data out of source | ❌ | ✅ (code) / ⚠️ (Git history) | Profile starts empty, or is seeded from a gitignored `profile_seed.json`; history rewrite is your decision |
| Profile | CRUD | ✅ | ✅ | |
| Profile | Missing-info warnings, CGPA-vs-resume check (S4) | ⬜ | ✅ | `/api/profile/completeness`; tests plus browser check |
| Profile | Backlogs, work authorisation, work mode, projects editor (S4) | ⬜ | ✅ | Tests |
| Resumes | Resume → profile import with per-field review and evidence (S4) | ⬜ | ✅ | Tests plus browser check |
| Resumes | Upload / parse / activate / delete | ✅ | ✅ | |
| Resumes | Skill extraction accuracy | ❌ (false positives) | 🟡 | Ambiguous patterns removed (test); section-aware extraction is Stage 4 |
| Discovery | Connectors (Arbeitnow, Jobicy, Remotive, WWR, Simplify, Adzuna) | 🟡 | 🟡 | Parsers unit-tested with fixture payloads. **Simplify verified live** (real listings, posted dates 2026-09 to 11). Arbeitnow, Jobicy, Remotive and WWR are **⛔** (blocked by the sandbox proxy); verify on your machine |
| Discovery | "Remote in USA/UK/Canada" treated as not open to India | ❌ (counted as eligible) | ✅ | Live Simplify run: 91 of 94 "eligible" listings were country-restricted remote; now 3 genuinely India-accessible remain (tests) |
| Discovery | No fabricated fields | ❌ | ✅ | Salary, company and work-mode fallbacks removed (tests) |
| Discovery | Dedupe without crash, source-scoped IDs | ❌ | ✅ | Regression test for `MultipleResultsFound` |
| Discovery | Source health: persisted per-source history, dashboard panel (S3) | ⬜ | ✅ | `source_runs` / `discovery_runs` tables, `/api/discovery/health`; rendered and checked in a browser with live data |
| Discovery | Retries, backoff, 429 Retry-After, pagination (S3) | ⬜ | ✅ | Mocked-HTTP tests; live run shows "after 4 attempts" errors for blocked hosts |
| Discovery | Expiry detection (S3) | ⬜ | 🟡 | ✅ for Simplify closed flags and complete career-board snapshots (tests). Other feeds have no closure evidence, so no expiry (by design) |
| Discovery | Company career boards: Greenhouse / Lever / Ashby (S3) | ⬜ | 🟡 | Parsers tested against documented formats; **live ⛔** in sandbox |
| Discovery | Background runs with progress; interrupted runs recorded (S3) | ⬜ | ✅ | Tests plus live run |
| Discovery | Indexed dedupe key, last_seen_at (S3) | ⬜ | ✅ | Tests; live second run: 3/3 duplicates detected |
| Analysis | Mode B text / URL / file | 🟡 (text broken in UI) | ✅ | Contract fixed (test) |
| Analysis | Requirements with explicit / inferred / missing and quoted evidence (S4) | ❌ | ✅ | `agents/requirements.py`; tests (excluded batches, % cut-offs, backlogs, work auth, relocation, duration) |
| Analysis | Title/company without the language model (S4) | ❌ | ✅ | Test |
| Eligibility | 10 dimensions, evidence per check, unknown never PASS (S4) | ❌ | ✅ | Tests; persisted in full (`checks_json`) |
| Matching | 5-factor score, per-factor reasons, N/A rescaling, real project overlap, next action (S4) | 🟡 | ✅ | Tests |
| Matching | Rankings: hard failures below eligible jobs | ❌ (pure score sort) | ✅ | PASS → UNKNOWN → FAIL, then score (test) |
| Applications | Draft generation, grounded answers | 🟡 | ✅ | `NEEDS_YOUR_INPUT` instead of invented answers (test) |
| Applications | Draft versions + restore (S5) | ⬜ | ✅ | Tests plus browser check |
| Applications | Grounding checker + approval gate (S5) | ⬜ | ✅ | Tests; rule-based, see limitations in PROGRESS.md |
| Approvals | Real match/eligibility, editable answers (S5) | ❌ (fake 90%/PASS) | ✅ | Browser check |
| Applications | Never overwrite a submitted application | ❌ | ✅ | Test |
| Approvals | Approve / reject from UI | ❌ (422) | ✅ | Contract fixed, `Literal` validation (test) |
| Browser | Approval gate before submit | ❌ | ✅ | 409 unless approved and confirmed (test) |
| Browser | No fabricated answers / sensitive attestations | ❌ | ✅ | Auto yes/no radios and textarea fallback removed (Playwright test) |
| Browser | Truthful submission verification | ❌ | ✅ | Before/after visible-text diff; otherwise `submission_unverified` (Playwright test) |
| Browser | Duplicate-submission guard | ⬜ | ✅ | Test |
| Browser | Emergency stop | ✅ | ✅ | Existing test |
| Browser | Label-based field mapping + per-field plan (S6) | ⬜ | ✅ | Playwright tests on Greenhouse/Lever/Ashby-style pages |
| Browser | Sensitive-question classifier (never auto-answered) (S6) | 🟡 | ✅ | 16 classifier cases plus browser tests |
| Browser | Site adapters Greenhouse / Lever / Ashby / generic; unsupported sites explained (S6) | ⬜ | 🟡 | Tested on reconstructed markup; **real sites ⛔** in sandbox. Preview a real posting first |
| Browser | Preview mode (types nothing), form state saved (S6) | ⬜ | ✅ | Tests plus browser check |
| Browser | Prepared-application export for manual sites (S6) | ⬜ | ✅ | Test plus browser check |
| Browser | Emergency stop = persistent halt of browser, discovery and schedule, with Resume (S6) | 🟡 | ✅ | Test (423 on every automation path) plus browser check |
| Tracker | 14-stage lifecycle, enforced transitions, event history (S5) | ⬜ | ✅ | Tests |
| Tracker | Filters, search, sort, pagination, notes, confirmation ID, follow-up date (S5) | ⬜ | ✅ | Tests plus browser check |
| Tracker | Shortlist from Opportunities; one application per job (S5) | ⬜ | ✅ | Tests |
| Scheduler | Persisted, starts at boot, overlap-safe | ❌ | ✅ | Tests |
| Scheduler | Daily (your timezone) or every 3/4/6/8/12/24 h; restored at boot and after Resume; refuses to start while halted (S7) | ⬜ | ✅ | Tests plus browser check |
| Scheduler | Run history (last 10) and 7-day failure count in Settings and Dashboard (S7) | ⬜ | ✅ | Tests plus browser check |
| Reports | Per-day accurate numbers, local-day window (Asia/Kolkata default, `TIMEZONE` setting) (S7) | ❌ (cumulative) | ✅ | Tests (boundary jobs either side of local midnight) |
| Reports | GET read-only, POST saves snapshot; history; date picker (S7) | ❌ (GET wrote rows) | ✅ | Tests plus browser check |
| Reports | Follow-ups due (endpoint, Dashboard card, report section) (S7) | ⬜ | ✅ | Tests plus browser check |
| Frontend | Real data, no mocks | ✅ | ✅ | |
| Frontend | Opportunities from stored evaluations: eligibility badge and reasons, score, skills, next action, facets, sort, server-side pagination, shortlist/evaluate/prepare (S8) | ⬜ | ✅ | `GET /api/jobs/opportunities`; tests plus browser check (27 seeded jobs) |
| Frontend | Toasts and confirm dialog instead of `alert()`/`confirm()`; shared loading/empty/error states (S8) | ⬜ | ✅ | No `alert(`/`confirm(` left in `src/`; browser check |
| Frontend | Tab in URL hash: reload, bookmarks and the phone back button work (S8) | ⬜ | ✅ | Browser check |
| Mobile | Bottom nav fixed to the screen bottom (was rendering at the top), More menu, 52 px targets, safe areas, no horizontal overflow on any page at 390 px, pinch-zoom allowed (S8) | ❌ | ✅ | Browser check, iPhone-size viewport |
| PWA | PNG icons (192/512/maskable), 180 px apple-touch-icon, relative manifest that works at `/` and `/ui/`, network-first service worker, bundled fonts (S8) | 🟡 | ✅ | Tests (files served, PNG signatures) plus browser check |
| PWA | iPhone offline shell over HTTPS (mkcert; `docs/IPHONE.md`) (S8) | 🟡 | ⛔ | Documented and auto-enabled when certs exist; needs a real iPhone to verify |
| AI | Ollama health and generation | ⛔ | ⛔ | Ollama not available in the audit sandbox |

**Completion estimate:** about 38% at audit → 47% (Stage 2) → 54% (Stage 3) → 61% (Stage 4) → 68% (Stage 5) → 74% (Stage 6) → 79% (Stage 7) → 84% (Stage 8) → **about 89% after Stage 9** (security 50→90%, reliability 50→85%; real-iPhone, Windows and live-source checks still to do). Weighted over 18 feature areas totalling 120 points; see AUDIT_REPORT.md §7.
