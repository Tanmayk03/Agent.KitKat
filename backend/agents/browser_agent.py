"""
Agent KitKat - Playwright Browser Automation Agent

Flow for one application:
  1. Site adapter: unsupported sites (LinkedIn, Naukri, Workday, ...) are refused with an
     explanation; Lever/Ashby jobs are opened on their application URL.
  2. Stop at CAPTCHA / bot checks or login walls (never bypassed).
  3. Map the form by its LABELS (agents/form_mapper.py) and build a plan: what will be filled,
     what is sensitive (never answered), what needs your input.
  4. preview mode stops here (screenshot + plan). fill mode fills only planned fields, uploads
     your resume, pastes the approved cover letter, then re-reads the form.
  5. Required fields still empty -> paused for you. Otherwise a pre-submit screenshot.
  6. Submit only when the service layer passed the approval + confirmation gates; success only
     if a NEW confirmation message appears, else "submission_unverified".

No anti-detection tricks, no auto-answers to legal/demographic/work-authorisation questions.
Personal values are never written to logs.
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from backend.config import get_settings
from backend.schemas.browser import BrowserRunResult
from backend.agents.form_mapper import EXTRACT_FIELDS_JS, plan_fields, summarize_plan
from backend.agents.site_adapters import DETECT_FORM_JS, adapter_for

logger = logging.getLogger("agent_kitkat.browser_agent")
settings = get_settings()


class BrowserAutomationAgent:
    """Autonomous agent handling browser interaction for job applications."""

    def __init__(self):
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def get_active_session_ids(self) -> List[str]:
        return list(self._active_sessions.keys())

    async def emergency_stop(self) -> int:
        """Immediately close every active browser session."""
        async with self._lock:
            stopped_count = len(self._active_sessions)
            logger.warning("🚨 EMERGENCY STOP: terminating %d browser session(s)", stopped_count)
            for draft_id, session in list(self._active_sessions.items()):
                try:
                    task = session.get("task")
                    if task and not task.done():
                        task.cancel()
                    browser = session.get("browser")
                    if browser:
                        await browser.close()
                except Exception as e:
                    logger.error("Error closing browser for draft %s: %s", draft_id, e)
            self._active_sessions.clear()
            return stopped_count

    async def run_application_automation(
        self,
        draft_id: str,
        job_data: Dict[str, Any],
        draft_data: Dict[str, Any],
        resume_file_path: Optional[str] = None,
        auto_submit: bool = False,
        headless: Optional[bool] = None,
        mode: str = "fill",
    ) -> BrowserRunResult:
        """mode: 'preview' (map the form, change nothing) or 'fill' (fill, optionally submit)."""
        logs: List[str] = []
        is_headless = headless if headless is not None else settings.BROWSER_HEADLESS
        url = job_data.get("application_url") or ""
        base = dict(draft_id=draft_id, job_id=job_data.get("id") or "", company_name=job_data.get("company_name") or "Unknown Company",
                    job_title=job_data.get("title") or "Unknown Role", application_url=url)

        def log(msg: str):
            entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
            logs.append(entry)
            logger.info("Draft %s: %s", draft_id[:8], msg)

        def result(status: str, **kw) -> BrowserRunResult:
            return BrowserRunResult(**base, status=status, logs=logs, **kw)

        log(f"{'Preview' if mode == 'preview' else 'Fill'} for {base['job_title']} at {base['company_name']}"
            + (" (will submit after filling)" if auto_submit else ""))

        if not url.startswith(("http://", "https://", "file://")):
            log("❌ Invalid or missing application URL.")
            return result("failed", requires_human_intervention=True, intervention_reason="Invalid or missing application URL")

        adapter = adapter_for(url)
        if not adapter.supported:
            log(f"⛔ Unsupported site: {adapter.reason}")
            return result("unsupported_site", requires_human_intervention=True, adapter=adapter.name,
                          intervention_reason=f"{adapter.reason} Use 'Copy prepared application' and apply yourself, "
                                              "then mark it Submitted in the tracker.")

        screenshots_dir = os.path.join(settings.SCREENSHOTS_DIR, draft_id)
        os.makedirs(screenshots_dir, exist_ok=True)
        pre_submit_path = os.path.join(screenshots_dir, "preview.png" if mode == "preview" else "pre_submit.png")
        post_submit_path = os.path.join(screenshots_dir, "post_submit.png")

        playwright_obj = None
        browser: Optional[Browser] = None
        current_task = asyncio.current_task()
        plan: List[Dict[str, Any]] = []
        adapter_name = adapter.name

        try:
            playwright_obj = await async_playwright().start()
            # No anti-detection flags: the agent never hides that it is automated.
            browser = await playwright_obj.chromium.launch(headless=is_headless)
            async with self._lock:
                self._active_sessions[draft_id] = {"task": current_task, "browser": browser, "draft_id": draft_id}
            context: BrowserContext = await browser.new_context(user_agent=settings.BROWSER_USER_AGENT,
                                                                viewport={"width": 1280, "height": 900})
            page: Page = await context.new_page()

            if adapter.apply_url != url:
                log(f"{adapter.note}: opening {adapter.apply_url}")
            try:
                await page.goto(adapter.apply_url, timeout=settings.BROWSER_TIMEOUT_MS, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)
            except PlaywrightTimeoutError:
                log("⚠️ Navigation timed out; checking what rendered.")
            log(f"Page loaded: {page.url}")

            has_captcha, captcha_desc = await self._detect_captcha(page)
            if has_captcha:
                log(f"🛑 CAPTCHA / bot check: {captcha_desc}. Not bypassing.")
                await page.screenshot(path=pre_submit_path, full_page=True)
                return result("paused_captcha", requires_human_intervention=True, adapter=adapter_name,
                              intervention_reason=f"CAPTCHA / bot verification ({captcha_desc}). Please complete it manually.",
                              pre_submit_screenshot=pre_submit_path)
            has_login, login_desc = await self._detect_login_wall(page)
            if has_login:
                log(f"🔒 Login required: {login_desc}")
                await page.screenshot(path=pre_submit_path, full_page=True)
                return result("paused_login", requires_human_intervention=True, adapter=adapter_name,
                              intervention_reason=f"Login or authentication required ({login_desc}).",
                              pre_submit_screenshot=pre_submit_path)

            detected = await page.evaluate(DETECT_FORM_JS)
            if detected and adapter_name == "generic":
                adapter_name = detected
                log(f"Recognised a {detected.title()} application form.")

            resume_ok = bool(resume_file_path and os.path.exists(resume_file_path))
            fields = await page.evaluate(EXTRACT_FIELDS_JS)
            plan = plan_fields(fields, draft_data, resume_ok)
            summary = summarize_plan(plan)
            log(f"Mapped {len(plan)} form field(s): " + ", ".join(f"{k}={v}" for k, v in summary.items()))
            if not plan:
                await page.screenshot(path=pre_submit_path, full_page=True)
                return result("failed", requires_human_intervention=True, adapter=adapter_name,
                              intervention_reason="No application form found on this page.", pre_submit_screenshot=pre_submit_path)

            if mode == "preview":
                await page.screenshot(path=pre_submit_path, full_page=True)
                log("Preview only: nothing was typed or clicked.")
                return result("previewed", requires_human_intervention=False, adapter=adapter_name,
                              form_plan=plan, form_summary=summary, pre_submit_screenshot=pre_submit_path)

            # ---- fill ---------------------------------------------------------------------
            await self._apply_plan(page, plan, resume_file_path, log)

            # Re-read the form: what required questions are still empty?
            after = await page.evaluate(EXTRACT_FIELDS_JS)
            unfilled = self._required_unfilled(after)
            summary = summarize_plan(plan)
            await page.screenshot(path=pre_submit_path, full_page=True)
            log("Pre-submit screenshot saved.")
            if unfilled:
                log(f"⚠️ Required questions need you: {', '.join(unfilled)}")
                return result("paused_unknown_field", requires_human_intervention=True, adapter=adapter_name,
                              intervention_reason=f"Required questions need your answer: {', '.join(unfilled)}",
                              form_plan=plan, form_summary=summary, pre_submit_screenshot=pre_submit_path)

            if not auto_submit:
                log("Filled. Waiting for your review (nothing submitted).")
                return result("filled_ready_for_review", requires_human_intervention=True, adapter=adapter_name,
                              intervention_reason="Application filled and ready for your final review.",
                              form_plan=plan, form_summary=summary, pre_submit_screenshot=pre_submit_path)

            submit_button = await self._find_submit_button(page)
            if not submit_button:
                log("⚠️ Could not reliably identify the submit button.")
                return result("filled_ready_for_review", requires_human_intervention=True, adapter=adapter_name,
                              intervention_reason="Could not reliably locate the submit button. Please submit manually.",
                              form_plan=plan, form_summary=summary, pre_submit_screenshot=pre_submit_path)

            pre_click_text = await self._visible_text(page)
            pre_click_url = page.url
            log("Submitting application (you approved and confirmed this submission)...")
            try:
                await submit_button.click()
                await page.wait_for_timeout(3000)
            except Exception as e:
                log(f"Error clicking submit: {e}")
                return result("failed", requires_human_intervention=True, adapter=adapter_name,
                              intervention_reason=f"Failed to trigger submission: {e}",
                              form_plan=plan, form_summary=summary, pre_submit_screenshot=pre_submit_path)

            await page.screenshot(path=post_submit_path, full_page=True)
            confirmed, phrase = await self._verify_submission_confirmation(page, pre_click_text, pre_click_url)
            if confirmed:
                log(f"🎉 Website confirmed submission: '{phrase}'")
                return result("submitted", requires_human_intervention=False, adapter=adapter_name, form_plan=plan,
                              form_summary=summary, pre_submit_screenshot=pre_submit_path, post_submit_screenshot=post_submit_path)
            log("⚠️ No new confirmation message after clicking Submit.")
            return result("submission_unverified", requires_human_intervention=True, adapter=adapter_name,
                          intervention_reason=("The submit button was clicked, but no new confirmation message appeared. "
                                               "Check your email or the site before assuming it was received."),
                          form_plan=plan, form_summary=summary, pre_submit_screenshot=pre_submit_path,
                          post_submit_screenshot=post_submit_path)

        except asyncio.CancelledError:
            log("🚨 Cancelled by Emergency Stop.")
            return result("halted_emergency", requires_human_intervention=True, adapter=adapter_name,
                          intervention_reason="Emergency stop triggered by user.", form_plan=plan)
        except Exception as e:
            log(f"❌ Unexpected browser error: {e}")
            return result("failed", requires_human_intervention=True, adapter=adapter_name,
                          intervention_reason=f"Automation error: {e}", form_plan=plan)
        finally:
            async with self._lock:
                self._active_sessions.pop(draft_id, None)
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright_obj:
                try:
                    await playwright_obj.stop()
                except Exception:
                    pass

    async def _apply_plan(self, page: Page, plan: List[Dict[str, Any]], resume_file_path: Optional[str], log) -> None:
        """Perform only the planned fill/select/upload actions; record the outcome per field."""
        for entry in plan:
            action = entry["action"]
            if action not in ("fill", "select", "upload"):
                entry["result"] = "left for you" if action in ("manual", "sensitive", "needs_input") else "unchanged"
                continue
            loc = page.locator(f'[data-kk="{entry["kk"]}"]').first
            try:
                if action == "upload":
                    await loc.set_input_files(resume_file_path)
                elif action == "select":
                    await loc.select_option(label=entry["value"])
                else:
                    await loc.fill(str(entry["value"]))
                entry["result"] = "done"
                log(f"{'Uploaded resume to' if action == 'upload' else 'Filled'} '{entry['label'][:60]}'")
            except Exception as e:
                entry["result"] = f"failed: {str(e)[:120]}"
                log(f"⚠️ Could not fill '{entry['label'][:60]}': {str(e)[:120]}")

    @staticmethod
    def _required_unfilled(fields: List[Dict[str, Any]]) -> List[str]:
        """Labels of required questions that are still empty (radio groups count once)."""
        missing, groups = [], {}
        for f in fields:
            if not f.get("required"):
                continue
            if f.get("type") == "radio":
                key = f.get("name") or f.get("question")
                groups.setdefault(key, {"label": f.get("question") or f.get("name"), "ok": False})
                groups[key]["ok"] = groups[key]["ok"] or f.get("has_value")
            elif not f.get("has_value"):
                missing.append(f.get("question") or f.get("label") or f.get("name") or f"field {f.get('kk')}")
        missing += [g["label"] for g in groups.values() if not g["ok"]]
        return [m[:80] for m in missing]

    async def _detect_captcha(self, page: Page) -> Tuple[bool, str]:
        """Detect presence of CAPTCHA or bot verification gates."""
        # Check iframe selectors
        captcha_selectors = [
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            "iframe[src*='challenges.cloudflare.com']",
            "iframe[src*='turnstile']",
            ".g-recaptcha",
            ".h-captcha",
            "#challenge-stage",
            ".cf-turnstile",
            ".cf-browser-verification",
            "#cf-wrapper"
        ]

        for sel in captcha_selectors:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    return True, f"Found selector '{sel}'"
            except Exception:
                pass

        # Check page text for common challenge phrases
        try:
            content = await page.content()
            content_lower = content.lower()
            suspicious_phrases = [
                "verify you are human",
                "prove you are not a robot",
                "please complete the security check",
                "cloudflare turnstile",
                "attention required! | cloudflare",
                "access denied - security check"
            ]
            for phrase in suspicious_phrases:
                if phrase in content_lower:
                    return True, f"Challenge text detected: '{phrase}'"
        except Exception:
            pass

        return False, ""

    async def _detect_login_wall(self, page: Page) -> Tuple[bool, str]:
        """Detect if the page requires authentication/sign-in to proceed."""
        current_url = page.url.lower()

        # Check URL indicators
        login_url_indicators = ["/login", "/signin", "/auth/login", "accounts.google.com", "linkedin.com/login"]
        for ind in login_url_indicators:
            if ind in current_url:
                return True, f"URL indicates authentication required: {ind}"

        # Check if page is asking for password
        try:
            pwd_inputs = await page.locator("input[type='password']").count()
            # If password field is present and no standard application fields exist
            if pwd_inputs > 0:
                name_inputs = await page.locator("input[name*='name' i]").count()
                if name_inputs == 0:
                    return True, "Password input field detected on login page"
        except Exception:
            pass

        return False, ""

    async def _find_submit_button(self, page: Page) -> Optional[Any]:
        """Identify submit button using standard ATS patterns."""
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit Application')",
            "button:has-text('Submit')",
            "button:has-text('Apply Now')",
            "button:has-text('Send Application')",
            "button:has-text('Complete Application')"
        ]

        for sel in submit_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return loc
            except Exception:
                pass

        return None

    @staticmethod
    async def _visible_text(page: Page) -> str:
        try:
            return (await page.locator("body").inner_text(timeout=5000)).lower()
        except Exception:
            return ""

    SUCCESS_PHRASES = [
        "thank you for applying",
        "thanks for applying",
        "application submitted",
        "application received",
        "application has been received",
        "we have received your application",
        "we've received your application",
        "your application has been sent",
        "your application has been submitted",
        "successfully submitted",
        "application complete",
    ]

    async def _verify_submission_confirmation(self, page: Page, pre_text: str = "", pre_url: str = "") -> Tuple[bool, str]:
        """
        Confirmed only if a success phrase is VISIBLE after the click and was NOT visible before it.
        (Many forms show "thanks for your interest" before submission; raw HTML and scripts are ignored.)
        """
        post_text = await self._visible_text(page)
        for phrase in self.SUCCESS_PHRASES:
            if phrase in post_text and phrase not in pre_text:
                return True, phrase
        return False, ""


# Singleton instance
browser_agent = BrowserAutomationAgent()
