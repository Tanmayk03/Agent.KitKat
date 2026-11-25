"""
Agent KitKat - Application form mapper.

1. EXTRACT_FIELDS_JS runs in the page and returns one descriptor per visible form control
   (plus hidden file inputs), with the human-readable question text found via <label for>,
   a wrapping <label>, aria-label / aria-labelledby, fieldset legend or nearby text. Each
   element is tagged with data-kk="<n>" so it can be targeted exactly later.
2. classify_field() decides what a field is from that text (never from a single name substring):
   a profile value, the resume upload, the cover letter, a screening answer, a SENSITIVE
   question (always left to you), or unknown.
3. plan_fields() pairs each field with the value Agent KitKat would put in it, so the plan can
   be previewed before anything is typed.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

EXTRACT_FIELDS_JS = r"""
() => {
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim().slice(0, 300);
  const visible = (el) => {
    const st = getComputedStyle(el);
    return st.visibility !== 'hidden' && st.display !== 'none' && (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const labelFor = (el) => {
    let t = '';
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) t = l.innerText;
    }
    if (!t) { const l = el.closest('label'); if (l) t = l.innerText; }
    if (!t && el.getAttribute('aria-label')) t = el.getAttribute('aria-label');
    if (!t && el.getAttribute('aria-labelledby')) {
      t = el.getAttribute('aria-labelledby').split(/\s+/).map((id) => (document.getElementById(id) || {}).innerText || '').join(' ');
    }
    if (!t) {
      let p = el.parentElement;
      for (let k = 0; k < 3 && p && !t; k++) {
        const lab = p.querySelector('label, legend, .application-label, .field-label, [class*="label"]');
        if (lab && !lab.contains(el)) t = lab.innerText;
        p = p.parentElement;
      }
    }
    return clean(t);
  };
  const questionFor = (el) => {
    // For radios/checkboxes: the question is usually a fieldset legend or the text just before the options
    const fs = el.closest('fieldset');
    if (fs) { const lg = fs.querySelector('legend'); if (lg) return clean(lg.innerText); }
    let node = el.closest('label') || el;
    for (let k = 0; k < 6 && node; k++) {
      let prev = node.previousElementSibling;
      while (prev) {
        const txt = clean(prev.innerText);
        if (txt && !prev.querySelector('input,select,textarea')) return txt;
        prev = prev.previousElementSibling;
      }
      node = node.parentElement;
      if (node && node.tagName === 'FORM') break;
    }
    return '';
  };
  const out = [];
  let i = 0;
  for (const el of document.querySelectorAll('input, textarea, select')) {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || (tag === 'input' ? 'text' : tag)).toLowerCase();
    if (['hidden', 'submit', 'button', 'image', 'reset', 'search'].includes(type)) continue;
    if (el.disabled) continue;
    if (type !== 'file' && !visible(el)) continue;
    el.setAttribute('data-kk', String(i));
    const isChoice = type === 'radio' || type === 'checkbox';
    out.push({
      kk: i, tag, type,
      name: el.getAttribute('name') || '',
      id: el.id || '',
      label: labelFor(el),
      question: isChoice ? questionFor(el) : '',
      placeholder: el.getAttribute('placeholder') || '',
      autocomplete: el.getAttribute('autocomplete') || '',
      required: !!(el.required || el.getAttribute('aria-required') === 'true'),
      has_value: isChoice ? el.checked : !!(el.value && el.value.trim()),
      option_value: isChoice ? (el.value || '') : '',
      options: tag === 'select' ? Array.from(el.options).map((o) => clean(o.text)).slice(0, 60) : [],
      accept: el.getAttribute('accept') || '',
    });
    i++;
  }
  return out;
}
"""

# Questions Agent KitKat must never answer for you
SENSITIVE_PATTERNS = [
    r"\bgender\b", r"\bsex\b", r"\brace\b", r"\bethnic", r"\bhispanic\b", r"\blatino", r"\bveteran", r"\bdisab",
    r"sexual orientation", r"\bpronoun", r"\breligio", r"\bcaste\b", r"\bcriminal\b", r"\bconvict", r"\bbackground (?:check|verification)",
    r"authori[sz]ed to work", r"work authori[sz]ation", r"\bvisa\b", r"\bsponsor", r"\bcitizenship\b", r"\bnationality\b",
    r"date of birth", r"\bdob\b", r"\bage\b", r"marital", r"salary history", r"current (?:ctc|salary)",
    r"\bconsent\b", r"\bi agree\b", r"\bi certify\b", r"\bi declare\b", r"\backnowledg", r"\bterms\b", r"privacy (?:policy|notice)",
    r"\bgdpr\b", r"\battest", r"\bdeclaration\b", r"\bself[- ]identif", r"\beeo\b", r"equal (?:employment|opportunity)",
]
_SENSITIVE_RE = re.compile("|".join(SENSITIVE_PATTERNS), re.IGNORECASE)

# (key, patterns). Order matters: more specific first.
PROFILE_KEYS: List[Tuple[str, List[str]]] = [
    ("first_name", [r"first[\s_-]*name", r"given[\s_-]*name", r"\bfname\b"]),
    ("last_name", [r"last[\s_-]*name", r"family[\s_-]*name", r"surname", r"\blname\b"]),
    ("email", [r"e-?mail"]),
    ("phone", [r"phone", r"mobile", r"contact number", r"\btel\b"]),
    ("linkedin_url", [r"linked[\s_-]*in"]),
    ("github_url", [r"git[\s_-]*hub"]),
    ("portfolio_url", [r"portfolio", r"personal (?:web)?site", r"\bwebsite\b", r"\bblog\b"]),
    ("graduation_year", [r"graduat", r"passing year", r"year of passing", r"\bgrad(?:uation)? (?:date|year)\b", r"class of"]),
    ("cgpa", [r"\bc?gpa\b", r"grade point", r"\bcgpa\b"]),
    ("university", [r"universit", r"\bcollege\b", r"\bschool\b", r"institut"]),
    ("major", [r"\bmajor\b", r"discipline", r"field of study", r"specializ", r"specialis", r"\bbranch\b"]),
    ("degree", [r"\bdegree\b", r"qualification"]),
    ("location", [r"\bcity\b", r"current location", r"\blocation\b", r"where are you (?:based|located)"]),
    ("full_name", [r"full[\s_-]*name", r"^name\b", r"\byour name\b", r"^\s*name\s*\*?$", r"_systemfield_name", r"legal name"]),
]
ANSWER_KEYS: List[Tuple[str, List[str]]] = [
    ("why_join", [r"why (?:do you want|are you interested|.*join)", r"what interests you", r"motivation"]),
    ("relevant_project", [r"relevant project", r"project you", r"tell us about a project", r"proud of"]),
    ("availability", [r"availab", r"start date", r"when can you (?:start|join)", r"notice period"]),
    ("salary_expectation", [r"expect(?:ed|ation).{0,20}(?:salary|stipend|compensation|ctc)", r"(?:salary|stipend|compensation) expect"]),
]


def field_text(f: Dict[str, Any]) -> str:
    parts = [f.get("question"), f.get("label"), f.get("placeholder"), f.get("name"), f.get("id"), f.get("autocomplete")]
    return " ".join(str(p) for p in parts if p).replace("_", " ").replace("[", " ").replace("]", " ").lower()


def classify_field(f: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Returns (kind, key):
      ("sensitive", None)        never auto-answered
      ("resume", None)           resume file upload
      ("cover_letter", None)     cover letter text area
      ("cover_letter_file", None) cover letter upload (left for you)
      ("profile", key)           a profile value (first_name, email, ...)
      ("answer", key)            a prepared screening answer
      ("unknown", None)          not recognised: left for you
    """
    text = field_text(f)
    ftype = (f.get("type") or "").lower()
    if _SENSITIVE_RE.search(text):
        return "sensitive", None
    if ftype == "file":
        if re.search(r"cover", text):
            return "cover_letter_file", None
        if re.search(r"resume|\bcv\b|curriculum", text) or not text.strip():
            return "resume", None
        return "unknown", None
    if ftype in ("radio", "checkbox"):
        return "unknown", None  # choice questions are always yours to answer
    if re.search(r"cover\s*letter", text):
        return "cover_letter", None
    for key, pats in ANSWER_KEYS:
        if any(re.search(p, text) for p in pats):
            return "answer", key
    autocomplete_map = {"given-name": "first_name", "family-name": "last_name", "name": "full_name", "email": "email", "tel": "phone"}
    if f.get("autocomplete") in autocomplete_map:
        return "profile", autocomplete_map[f["autocomplete"]]
    if ftype == "email":
        return "profile", "email"
    if ftype == "tel":
        return "profile", "phone"
    for key, pats in PROFILE_KEYS:
        if any(re.search(p, text) for p in pats):
            return "profile", key
    return "unknown", None


def _pick_option(options: List[str], value: str) -> Optional[str]:
    v = value.lower().strip()
    if not v:
        return None
    for opt in options:
        if opt.lower().strip() == v:
            return opt
    for opt in options:
        o = opt.lower()
        if o and (v in o or o in v) and len(o) > 1 and not o.startswith("select"):
            return opt
    return None


def plan_fields(fields: List[Dict[str, Any]], draft: Dict[str, Any], resume_available: bool) -> List[Dict[str, Any]]:
    """
    Decide, per field, what would happen. action is one of:
      fill / upload / select   - Agent KitKat will do it (value shown)
      keep                     - field already has a value
      needs_input              - recognised, but your profile/draft has no value
      sensitive                - never auto-answered
      manual                   - unknown / choice question: left for you
    """
    form_values = draft.get("form_field_values") or {}
    answers = draft.get("custom_answers") or {}
    letter = draft.get("cover_letter") or ""
    plan = []
    for f in fields:
        kind, key = classify_field(f)
        raw_label = f.get("question") or f.get("label") or f.get("placeholder") or f.get("name") or f"field {f['kk']}"
        entry = {
            "kk": f["kk"], "label": re.sub(r"[\s*✱]+$", "", raw_label).strip() or raw_label,
            "option": f.get("label") if f.get("type") in ("radio", "checkbox") else None,
            "type": f.get("type"), "required": bool(f.get("required")), "kind": kind, "key": key,
            "action": "manual", "value": None, "reason": None,
        }
        if f.get("has_value") and kind not in ("resume",):
            entry.update(action="keep", reason="Already has a value")
        elif kind == "sensitive":
            entry.update(action="sensitive", reason="Personal/legal question: answer it yourself")
        elif kind == "resume":
            entry.update(action="upload" if resume_available else "needs_input",
                         reason=None if resume_available else "No active resume file")
        elif kind == "cover_letter":
            entry.update(action="fill" if letter else "needs_input", value=letter or None)
        elif kind == "cover_letter_file":
            entry.update(action="manual", reason="Cover letter upload: attach a file yourself if you want one")
        elif kind == "answer":
            val = answers.get(key)
            if val and val != "NEEDS_YOUR_INPUT":
                entry.update(action="fill", value=val)
            else:
                entry.update(action="needs_input", reason="Write this answer in Approvals first")
        elif kind == "profile":
            val = str(form_values.get(key) or "")
            if not val:
                entry.update(action="needs_input", reason=f"'{key}' is empty in your profile")
            elif f.get("tag") == "select":
                opt = _pick_option(f.get("options") or [], val)
                if opt:
                    entry.update(action="select", value=opt)
                else:
                    entry.update(action="manual", reason=f"No option matches '{val}'")
            else:
                entry.update(action="fill", value=val)
        else:
            entry.update(action="manual", reason="Not recognised: answer it yourself")
        plan.append(entry)
    return plan


def summarize_plan(plan: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for p in plan:
        out[p["action"]] = out.get(p["action"], 0) + 1
    out["required_left_for_you"] = sum(1 for p in plan if p["required"] and p["action"] in ("manual", "sensitive", "needs_input"))
    return out
