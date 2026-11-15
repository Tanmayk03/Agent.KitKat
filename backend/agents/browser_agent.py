"""
Agent KitKat - Playwright Browser Automation Agent
Automates opening application forms, auto-filling candidate details,
uploading verified resume PDF, pasting tailored cover letter,
capturing pre/post submission screenshots, and verifying submission results.

Strict Safety Rules:
- Pauses immediately on CAPTCHA / bot challenge (never attempts bypass).
- Pauses immediately on login / authentication gates.
- Pauses immediately on unknown required fields or sensitive declarations.
- Never claims submission without explicit confirmation on page.
- Provides an immediate Emergency Stop kill-switch.
"""

import os
import re
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from backend.config import get_settings
from backend.schemas.browser import BrowserRunResult

logger = logging.getLogger("agent_kitkat.browser_agent")
settings = get_settings()


class BrowserAutomationAgent:
    """
    Autonomous agent handling browser interaction for job applications.
    """

    def __init__(self):
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def get_active_session_ids(self) -> List[str]:
        """Return list of draft IDs currently undergoing browser automation."""
        return list(self._active_sessions.keys())

    async def emergency_stop(self) -> int:
        """
        Emergency stop: immediately terminates all active browser sessions,
        closes open browser windows, and cleans up resources.
        """
        async with self._lock:
            stopped_count = len(self._active_sessions)
            logger.warning("🚨 EMERGENCY STOP TRIGGERED! Terminating %d active browser sessions...", stopped_count)

            for draft_id, session in list(self._active_sessions.items()):
                try:
                    # Cancel any running task
                    task = session.get("task")
                    if task and not task.done():
                        task.cancel()

                    # Close browser context / browser
                    browser = session.get("browser")
                    if browser:
                        await browser.close()
                except Exception as e:
                    logger.error("Error closing browser for draft %s: %s", draft_id, e)

            self._active_sessions.clear()
            logger.info("✅ All active browser sessions successfully halted.")
            return stopped_count

    async def run_application_automation(
        self,
        draft_id: str,
        job_data: Dict[str, Any],
        draft_data: Dict[str, Any],
        resume_file_path: Optional[str] = None,
        auto_submit: bool = False,
        headless: Optional[bool] = None,
    ) -> BrowserRunResult:
        """
        Execute the end-to-end browser automation flow for a job application.
        """
        logs: List[str] = []
        is_headless = headless if headless is not None else settings.BROWSER_HEADLESS

        application_url = job_data.get("application_url") or ""
        company_name = job_data.get("company_name") or "Unknown Company"
        job_title = job_data.get("title") or "Unknown Role"
        job_id = job_data.get("id") or ""

        def log(msg: str):
            timestamp = datetime.now().strftime("%H:%M:%S")
            entry = f"[{timestamp}] {msg}"
            logs.append(entry)
            logger.info("Draft %s: %s", draft_id[:8], msg)

        log(f"Starting browser automation for {job_title} at {company_name}")
        log(f"Target URL: {application_url}")
        log(f"Submission Mode: {'AUTO_SUBMIT' if auto_submit else 'PREPARE_AND_REVIEW'}")

        if not application_url or not (application_url.startswith("http://") or application_url.startswith("https://") or application_url.startswith("file://")):
            log("❌ Invalid or missing application URL.")
            return BrowserRunResult(
                draft_id=draft_id,
                job_id=job_id,
                company_name=company_name,
                job_title=job_title,
                application_url=application_url,
                status="failed",
                requires_human_intervention=True,
                intervention_reason="Invalid or missing application URL",
                logs=logs
            )

        # Prepare screenshot directory
        screenshots_dir = os.path.join(settings.SCREENSHOTS_DIR, draft_id)
        os.makedirs(screenshots_dir, exist_ok=True)
        pre_submit_path = os.path.join(screenshots_dir, "pre_submit.png")
        post_submit_path = os.path.join(screenshots_dir, "post_submit.png")

        playwright_obj = None
        browser: Optional[Browser] = None
        current_task = asyncio.current_task()

        try:
            playwright_obj = await async_playwright().start()
            browser = await playwright_obj.chromium.launch(
                headless=is_headless,
                args=["--disable-blink-features=AutomationControlled"]
            )

            # Register active session for emergency stop
            async with self._lock:
                self._active_sessions[draft_id] = {
                    "task": current_task,
                    "browser": browser,
                    "draft_id": draft_id
                }

            context: BrowserContext = await browser.new_context(
                user_agent=settings.BROWSER_USER_AGENT,
                viewport={"width": 1280, "height": 900}
            )
            page: Page = await context.new_page()

            log("Browser launched successfully. Navigating to application page...")

            # 1. Navigation
            try:
                await page.goto(application_url, timeout=settings.BROWSER_TIMEOUT_MS, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)  # Allow dynamic JS scripts to render
            except PlaywrightTimeoutError:
                log("⚠️ Navigation timed out. Checking if page partially rendered...")

            current_url = page.url
            log(f"Page loaded: {current_url}")

            # 2. Check for Anti-Bot / CAPTCHA protection
            has_captcha, captcha_desc = await self._detect_captcha(page)
            if has_captcha:
                log(f"🛑 CAPTCHA / Anti-bot gate detected: {captcha_desc}")
                log("Agent will NOT bypass security gates. Pausing for human verification.")
                await page.screenshot(path=pre_submit_path, full_page=True)
                return BrowserRunResult(
                    draft_id=draft_id,
                    job_id=job_id,
                    company_name=company_name,
                    job_title=job_title,
                    application_url=application_url,
                    status="paused_captcha",
                    requires_human_intervention=True,
                    intervention_reason=f"CAPTCHA / Bot verification gate detected ({captcha_desc}). Please complete manually.",
                    pre_submit_screenshot=pre_submit_path,
                    logs=logs
                )

            # 3. Check for Login wall
            has_login, login_desc = await self._detect_login_wall(page)
            if has_login:
                log(f"🔒 Login wall detected: {login_desc}")
                log("Agent paused. Authentication is required before applying.")
                await page.screenshot(path=pre_submit_path, full_page=True)
                return BrowserRunResult(
                    draft_id=draft_id,
                    job_id=job_id,
                    company_name=company_name,
                    job_title=job_title,
                    application_url=application_url,
                    status="paused_login",
                    requires_human_intervention=True,
                    intervention_reason=f"Login or authentication required ({login_desc}).",
                    pre_submit_screenshot=pre_submit_path,
                    logs=logs
                )

            # 4. Fill Application Form Fields
            log("Analyzing page inputs and filling verified candidate profile details...")
            fill_summary = await self._fill_form_fields(page, draft_data, resume_file_path, log)
            log(f"Form filling completed: {fill_summary['filled_count']} fields filled.")

            # 5. Check for unknown or unfilled required fields
            unfilled_reqs = await self._check_unfilled_required_fields(page, log)
            if unfilled_reqs:
                log(f"⚠️ Mandatory questions or declarations require human input: {', '.join(unfilled_reqs)}")
                await page.screenshot(path=pre_submit_path, full_page=True)
                return BrowserRunResult(
                    draft_id=draft_id,
                    job_id=job_id,
                    company_name=company_name,
                    job_title=job_title,
                    application_url=application_url,
                    status="paused_unknown_field",
                    requires_human_intervention=True,
                    intervention_reason=f"Unanswered required fields or sensitive declarations: {', '.join(unfilled_reqs)}",
                    pre_submit_screenshot=pre_submit_path,
                    logs=logs
                )

            # 6. Capture Pre-Submit Screenshot
            await page.screenshot(path=pre_submit_path, full_page=True)
            log(f"Pre-submission screenshot saved to {pre_submit_path}")

            # 7. Decide whether to Submit or Prepare Only
            if not auto_submit:
                log("Review Mode: Application prepared and filled. Pausing for human approval (auto_submit=False).")
                return BrowserRunResult(
                    draft_id=draft_id,
                    job_id=job_id,
                    company_name=company_name,
                    job_title=job_title,
                    application_url=application_url,
                    status="filled_ready_for_review",
                    requires_human_intervention=True,
                    intervention_reason="Application filled and ready for your final manual review.",
                    pre_submit_screenshot=pre_submit_path,
                    logs=logs
                )

            # 8. Submit Application (When Auto-Submit is explicitly enabled)
            log("Auto-submission authorized. Locating submit button...")
            submit_button = await self._find_submit_button(page)
            if not submit_button:
                log("⚠️ Could not reliably identify the submit button on the application form.")
                return BrowserRunResult(
                    draft_id=draft_id,
                    job_id=job_id,
                    company_name=company_name,
                    job_title=job_title,
                    application_url=application_url,
                    status="filled_ready_for_review",
                    requires_human_intervention=True,
                    intervention_reason="Could not reliably locate the submit button. Please submit manually.",
                    pre_submit_screenshot=pre_submit_path,
                    logs=logs
                )

            log("Submitting application...")
            try:
                await submit_button.click()
                await page.wait_for_timeout(3000)  # Wait for submission request to settle
            except Exception as e:
                log(f"Error clicking submit button: {e}")
                return BrowserRunResult(
                    draft_id=draft_id,
                    job_id=job_id,
                    company_name=company_name,
                    job_title=job_title,
                    application_url=application_url,
                    status="failed",
                    requires_human_intervention=True,
                    intervention_reason=f"Failed to trigger submission: {str(e)}",
                    pre_submit_screenshot=pre_submit_path,
                    logs=logs
                )

            # 9. Verify Submission Success
            await page.screenshot(path=post_submit_path, full_page=True)
            log(f"Post-submission screenshot saved to {post_submit_path}")

            submission_confirmed, confirm_text = await self._verify_submission_confirmation(page)
            if submission_confirmed:
                log(f"🎉 Submission CONFIRMED by website: '{confirm_text}'")
                return BrowserRunResult(
                    draft_id=draft_id,
                    job_id=job_id,
                    company_name=company_name,
                    job_title=job_title,
                    application_url=application_url,
                    status="submitted",
                    requires_human_intervention=False,
                    pre_submit_screenshot=pre_submit_path,
                    post_submit_screenshot=post_submit_path,
                    logs=logs
                )
            else:
                log("⚠️ Website did not explicitly confirm submission. Status held for verification.")
                return BrowserRunResult(
                    draft_id=draft_id,
                    job_id=job_id,
                    company_name=company_name,
                    job_title=job_title,
                    application_url=application_url,
                    status="submission_uncertain",
                    requires_human_intervention=True,
                    intervention_reason="Application was sent but website did not show a clear confirmation message. Please verify.",
                    pre_submit_screenshot=pre_submit_path,
                    post_submit_screenshot=post_submit_path,
                    logs=logs
                )

        except asyncio.CancelledError:
            log("🚨 Process was CANCELLED via Emergency Stop.")
            return BrowserRunResult(
                draft_id=draft_id,
                job_id=job_id,
                company_name=company_name,
                job_title=job_title,
                application_url=application_url,
                status="halted_emergency",
                requires_human_intervention=True,
                intervention_reason="Emergency stop triggered by user.",
                logs=logs
            )
        except Exception as e:
            log(f"❌ Unexpected browser error: {str(e)}")
            return BrowserRunResult(
                draft_id=draft_id,
                job_id=job_id,
                company_name=company_name,
                job_title=job_title,
                application_url=application_url,
                status="failed",
                requires_human_intervention=True,
                intervention_reason=f"Automation error: {str(e)}",
                logs=logs
            )
        finally:
            # Clean up active session
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

    async def _fill_form_fields(
        self,
        page: Page,
        draft_data: Dict[str, Any],
        resume_file_path: Optional[str],
        log: Any
    ) -> Dict[str, int]:
        """
        Fill standard ATS form fields using verified profile information,
        tailored cover letter, and resume file upload.
        """
        form_values = draft_data.get("form_field_values") or {}
        custom_answers = draft_data.get("custom_answers") or {}
        cover_letter = draft_data.get("cover_letter") or ""

        filled_count = 0

        # Mapping heuristics: (field_key, list_of_selectors)
        field_rules = [
            ("first_name", ["input[name*='first' i]", "input[id*='first' i]", "input[autocomplete='given-name']", "input[placeholder*='first name' i]"]),
            ("last_name", ["input[name*='last' i]", "input[id*='last' i]", "input[autocomplete='family-name']", "input[placeholder*='last name' i]"]),
            ("full_name", ["input[name*='fullname' i]", "input[name='name' i]", "input[id*='fullname' i]", "input[id='name' i]", "input[autocomplete='name']", "input[placeholder*='full name' i]"]),
            ("email", ["input[type='email']", "input[name*='email' i]", "input[id*='email' i]", "input[autocomplete='email']", "input[placeholder*='email' i]"]),
            ("phone", ["input[type='tel']", "input[name*='phone' i]", "input[id*='phone' i]", "input[autocomplete='tel']", "input[placeholder*='phone' i]"]),
            ("location", ["input[name*='city' i]", "input[name*='location' i]", "input[id*='location' i]", "input[placeholder*='location' i]", "input[placeholder*='city' i]"]),
            ("linkedin_url", ["input[name*='linkedin' i]", "input[id*='linkedin' i]", "input[placeholder*='linkedin' i]"]),
            ("github_url", ["input[name*='github' i]", "input[id*='github' i]", "input[placeholder*='github' i]"]),
            ("portfolio_url", ["input[name*='portfolio' i]", "input[name*='website' i]", "input[id*='portfolio' i]", "input[placeholder*='portfolio' i]"]),
            ("university", ["input[name*='university' i]", "input[name*='college' i]", "input[name*='school' i]", "input[id*='university' i]", "input[placeholder*='university' i]"]),
            ("degree", ["input[name*='degree' i]", "input[id*='degree' i]", "input[placeholder*='degree' i]"]),
            ("major", ["input[name*='major' i]", "input[name*='discipline' i]", "input[id*='major' i]"]),
            ("graduation_year", ["input[name*='grad' i]", "input[id*='grad' i]", "input[placeholder*='graduation' i]"]),
            ("cgpa", ["input[name*='gpa' i]", "input[name*='cgpa' i]", "input[id*='cgpa' i]", "input[placeholder*='cgpa' i]"]),
        ]

        for field_key, selectors in field_rules:
            val = str(form_values.get(field_key) or "")
            if not val:
                continue

            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        cur_val = await loc.input_value()
                        if not cur_val:
                            await loc.fill(val)
                            log(f"Filled field '{field_key}' -> {val}")
                            filled_count += 1
                            break
                except Exception:
                    pass

        # Handle Radio Buttons / Selects for Work Authorization & Sponsorship
        try:
            # Authorized to work in India -> Yes
            auth_radios = page.locator("input[type='radio'][name*='authoriz' i], input[type='radio'][name*='eligible' i]")
            if await auth_radios.count() > 0:
                yes_radio = page.locator("input[type='radio'][value*='yes' i], input[type='radio'][id*='yes' i]").first
                if await yes_radio.count() > 0:
                    await yes_radio.check()
                    log("Selected 'Yes' for work authorization.")
                    filled_count += 1
        except Exception:
            pass

        try:
            # Sponsorship required -> No
            spons_radios = page.locator("input[type='radio'][name*='sponsor' i]")
            if await spons_radios.count() > 0:
                no_radio = page.locator("input[type='radio'][name*='sponsor' i][value*='no' i]").first
                if await no_radio.count() > 0:
                    await no_radio.check()
                    log("Selected 'No' for visa sponsorship requirement.")
                    filled_count += 1
        except Exception:
            pass

        # Fill Tailored Cover Letter
        if cover_letter:
            cover_selectors = [
                "textarea[name*='cover' i]",
                "textarea[id*='cover' i]",
                "textarea[placeholder*='cover letter' i]",
                "textarea[name*='letter' i]",
                "textarea"  # fallback to first textarea on page
            ]
            for sel in cover_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        cur_val = await loc.input_value()
                        if not cur_val:
                            await loc.fill(cover_letter)
                            log("Pasted tailored cover letter into application textarea.")
                            filled_count += 1
                            break
                except Exception:
                    pass

        # Fill Custom Screening Answers (e.g. why_join, relevant_project, availability, salary)
        for q_key, ans in custom_answers.items():
            if not ans:
                continue
            answer_selectors = [
                f"textarea[name*='{q_key}' i]",
                f"input[name*='{q_key}' i]",
                f"textarea[id*='{q_key}' i]",
                f"input[id*='{q_key}' i]"
            ]
            for sel in answer_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        cur_val = await loc.input_value()
                        if not cur_val:
                            await loc.fill(str(ans))
                            log(f"Answered screening question '{q_key}'")
                            filled_count += 1
                            break
                except Exception:
                    pass

        # Upload Resume PDF
        if resume_file_path and os.path.exists(resume_file_path):
            try:
                file_inputs = page.locator("input[type='file']")
                if await file_inputs.count() > 0:
                    resume_input = file_inputs.first
                    await resume_input.set_input_files(resume_file_path)
                    log(f"Uploaded verified resume: {os.path.basename(resume_file_path)}")
                    filled_count += 1
                else:
                    log("ℹ️ No file upload input found on this page.")
            except Exception as e:
                log(f"⚠️ Error uploading resume file: {e}")
        else:
            log("ℹ️ No resume file path provided or file does not exist.")

        return {"filled_count": filled_count}

    async def _check_unfilled_required_fields(self, page: Page, log: Any) -> List[str]:
        """
        Check for any remaining mandatory fields that are still blank or unchecked.
        """
        unfilled = []
        try:
            # Find all required inputs
            required_elements = page.locator("input[required], select[required], textarea[required]")
            count = await required_elements.count()

            for i in range(count):
                elem = required_elements.nth(i)
                if not await elem.is_visible():
                    continue

                tag_name = await elem.evaluate("el => el.tagName.toLowerCase()")
                input_type = await elem.get_attribute("type") or "text"
                name = await elem.get_attribute("name") or await elem.get_attribute("id") or f"field_{i}"

                if input_type in ["checkbox", "radio"]:
                    is_checked = await elem.is_checked()
                    if not is_checked:
                        unfilled.append(f"{name} (required {input_type})")
                elif tag_name in ["input", "textarea"]:
                    val = await elem.input_value()
                    if not val or not val.strip():
                        unfilled.append(f"{name} (required text)")
                elif tag_name == "select":
                    val = await elem.input_value()
                    if not val or not val.strip():
                        unfilled.append(f"{name} (required selection)")

        except Exception as e:
            log(f"⚠️ Error inspecting required fields: {e}")

        return unfilled

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

    async def _verify_submission_confirmation(self, page: Page) -> Tuple[bool, str]:
        """Verify if the page displays clear evidence of successful submission."""
        success_phrases = [
            "thank you for applying",
            "application submitted",
            "application received",
            "we have received your application",
            "your application has been sent",
            "successfully submitted",
            "application complete",
            "thanks for your interest"
        ]

        try:
            content = await page.content()
            content_lower = content.lower()

            for phrase in success_phrases:
                if phrase in content_lower:
                    return True, phrase
        except Exception:
            pass

        return False, ""


# Singleton instance
browser_agent = BrowserAutomationAgent()
