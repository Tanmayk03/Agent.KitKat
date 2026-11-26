# Changelog

## [1.0.0-rc.1] - 2026-11-26

Release candidate: everything below is implemented and tested in the development sandbox. It still
needs to be run on Windows, on a real iPhone, and against the live job sites and Ollama (see
ACCEPTANCE.md). Details per stage are in PROGRESS.md.

### Safety and privacy
- New profiles default to **Prepare only**. Submitting needs your approval and a final
  per-application confirmation; the old "pre-authorized" policy is disabled.
- CAPTCHAs and logins pause the run and are never bypassed. Sensitive, legal and demographic
  questions are never answered.
- Emergency Stop is a persistent halt of the browser, discovery and the schedule, lifted with Resume.
- The backend listens on 127.0.0.1. CORS uses an allow-list and cross-site writes are refused.
  Other devices need the phone access code (QR pairing). Security headers added.
- Personal data was removed from the code and is masked in logs and stored browser logs.
- Uploads are sanitised and the URL fetcher refuses private addresses (SSRF guard).

### Features
- Discovery from SimplifyJobs, Arbeitnow, Jobicy, Remotive, We Work Remotely, Adzuna and company
  career boards (Greenhouse, Lever, Ashby). Includes duplicate and expiry detection and per-source
  health.
- Profile from your resume (skills verified only from the file) and a profile-health card.
- Eligibility with 10 evidence-backed checks, an explainable match score and next actions.
- Opportunities list from the evaluations, with filters, sorting and pages.
- Grounded drafts with version history and a check for unsupported claims.
- 14-stage tracker with history, notes, follow-ups and confirmation IDs.
- Label-based form filling for Greenhouse, Lever and Ashby, a read-only preview, and an export for
  sites that can't be automated.
- Discovery runs daily or every few hours. Per-day reports in your timezone. Follow-ups due.
- Mobile: bottom navigation, safe areas, PNG icons, network-first service worker, optional HTTPS.
- Daily automatic backups, `backup.bat` / `restore.bat`, and a rotating JSON log file.

### Install and tooling
- `install.bat` / `install.ps1` (installs from the tested lock file), `start.bat` with health
  waits, `test.ps1` (`-Live` adds the live checks).
- 198 pytest tests (11 of them live checks, run with `pytest -m live`) plus the legacy phase scripts, all on a temporary database.

### Removed
- `scripts/harvest_*.py`: they deleted all applications, drafts and approvals from your database.
  Use `scripts/run_discovery.py`, which never deletes and makes a backup first.
- `scripts/verify_real_data.py` (replaced by the read-only `scripts/db_summary.py`) and the stale
  `start_all_backup.ps1`.

## [0.2.0]
The project as it was before the audit (see AUDIT_REPORT.md).
