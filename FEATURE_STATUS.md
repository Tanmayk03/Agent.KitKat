# Feature Status — evidence-based

Legend: ✅ Working (demonstrated) · 🟡 Partial · 🧩 UI/placeholder only · ❌ Broken · ⬜ Missing · ⛔ Blocked (could not be verified in the audit environment)

Last updated: 2026-11-25, after Stage 5 (applications & tracking). Rows changed in Stages 3/4/5 are marked (S3)/(S4)/(S5). The "After Stage 2" column shows what changed. Details are in `PROGRESS.md`.

| Area | Feature | Before (audit) | After Stage 2 | Evidence / remaining gap |
|---|---|---|---|---|
| Platform | Backend boots, DB tables created | ✅ | ✅ | uvicorn boot plus 7 endpoints returned 200 |
| Platform | Frontend production build | ✅ | ✅ | `npm run build` OK |
| Platform | Tests isolated from the real DB | ❌ (tests wipe data) | ✅ | `tests/_isolation.py` sets the temp DB and storage before importing backend; `pytest` refuses the real DB |
| Platform | One-command install / test | 🟡 | 🟡 | `run_all_tests.ps1` now runs pytest; installer still to do (Stage 10) |
| Security | CORS / cross-site requests | ❌ (any origin) | ✅ | Allow-list of localhost and private-LAN origins; cross-site writes get 403 (test) |
| Security | LAN exposure / auth | ❌ | 🟡 | Backend now binds 127.0.0.1 by default; LAN access token still to do (Stage 9) |
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
| Browser | Site adapters (Greenhouse, Lever, Ashby…) | ⬜ | ⬜ | Stage 6 |
| Tracker | 14-stage lifecycle, enforced transitions, event history (S5) | ⬜ | ✅ | Tests |
| Tracker | Filters, search, sort, pagination, notes, confirmation ID, follow-up date (S5) | ⬜ | ✅ | Tests plus browser check |
| Tracker | Shortlist from Opportunities; one application per job (S5) | ⬜ | ✅ | Tests |
| Scheduler | Persisted, starts at boot, overlap-safe | ❌ | ✅ | Tests; interval scheduling is Stage 7 |
| Reports | Per-day accurate numbers | ❌ (cumulative) | ❌ | Stage 7 |
| Frontend | Real data, no mocks | ✅ | ✅ | |
| Frontend | Opportunities with score and eligibility, pagination, toasts | ⬜ | ⬜ | Stage 8 |
| PWA | iPhone install over LAN | 🟡 | 🟡 | Service workers need HTTPS on a LAN IP; Stage 8 |
| AI | Ollama health and generation | ⛔ | ⛔ | Ollama not available in the audit sandbox |

**Completion estimate:** about 38% at audit → 47% (Stage 2) → 54% (Stage 3) → 61% (Stage 4) → **about 68% after Stage 5**. Weighted over 18 feature areas totalling 120 points; see AUDIT_REPORT.md §7. Main Stage 5 gains: application preparation 30→85%, approvals & tracking 35→90%.
