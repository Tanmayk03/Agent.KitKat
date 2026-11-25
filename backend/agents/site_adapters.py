"""
Agent KitKat - Site adapters for application pages.

An adapter decides (a) whether Agent KitKat may automate a site at all, (b) which URL holds the
actual application form, and (c) how to recognise that form. Filling itself is label-based
(agents/form_mapper.py), so adapters stay small.

Unsupported sites are explained honestly: Agent KitKat does not log in, bypass CAPTCHAs or
work around anti-automation rules. For those you get a prepared application (export) and apply
yourself, then mark it Submitted in the tracker.
"""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

UNSUPPORTED = {
    "linkedin.com": "LinkedIn requires you to be logged in and does not allow automated applications.",
    "naukri.com": "Naukri requires login and blocks automated applications.",
    "indeed.com": "Indeed requires login and uses anti-bot checks.",
    "indeed.co.in": "Indeed requires login and uses anti-bot checks.",
    "internshala.com": "Internshala requires login; applications go through your Internshala account.",
    "myworkdayjobs.com": "Workday requires creating an account and logging in for every company.",
    "workday.com": "Workday requires creating an account and logging in.",
    "glassdoor.com": "Glassdoor requires login.",
    "glassdoor.co.in": "Glassdoor requires login.",
    "wellfound.com": "Wellfound requires login.",
    "angel.co": "Wellfound (AngelList) requires login.",
    "instahyre.com": "Instahyre requires login.",
    "foundit.in": "foundit requires login.",
    "unstop.com": "Unstop requires login.",
    "cutshort.io": "Cutshort requires login.",
    "hirist.tech": "Hirist requires login.",
}


@dataclass
class Adapter:
    name: str               # greenhouse | lever | ashby | generic | unsupported
    supported: bool
    apply_url: str
    reason: Optional[str] = None
    note: Optional[str] = None


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def adapter_for(url: str) -> Adapter:
    host = _host(url)
    for domain, reason in UNSUPPORTED.items():
        if host == domain or host.endswith("." + domain):
            return Adapter("unsupported", False, url, reason=reason)

    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io", "job-boards.eu.greenhouse.io"):
        # The application form is on the job page itself (#application_form / #app)
        return Adapter("greenhouse", True, url, note="Greenhouse hosted form")
    if host in ("jobs.lever.co", "jobs.eu.lever.co"):
        apply = url if path.endswith("/apply") else f"{parsed.scheme}://{parsed.netloc}{path}/apply"
        return Adapter("lever", True, apply, note="Lever hosted form (/apply)")
    if host == "jobs.ashbyhq.com":
        apply = url if path.endswith("/application") else f"{parsed.scheme}://{parsed.netloc}{path}/application"
        return Adapter("ashby", True, apply, note="Ashby hosted form (/application)")
    return Adapter("generic", True, url, note="Unknown site: fields are matched by their labels; review everything carefully")


DETECT_FORM_JS = r"""
() => {
  if (document.querySelector('#application_form, #application-form, input[name^="job_application["]')) return 'greenhouse';
  if (document.querySelector('input[name="urls[LinkedIn]"], form[action*="lever.co"], .application-page .application-form')) return 'lever';
  if (document.querySelector('input[name^="_systemfield_"], [class*="ashby-application-form"]')) return 'ashby';
  return null;
}
"""
