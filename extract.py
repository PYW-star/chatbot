# import json
# import re
# from datetime import datetime

# import anthropic

# client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

# MODEL = "claude-haiku-5-5"

# SYSTEM_TEMPLATE = """You turn messages from staff at a Malaysian corporate services firm into a list of Company Secretarial (CoSec) task records.

# Today's date is <<TODAY>> (YYYY-MM-DD).

# OUTPUT: only a JSON object. No explanation, no markdown fences.
# {
#   "intent": "new_task" | "update" | "unknown",
#   "tasks": [
#     {"company": string or null, "category": string or null, "date_received": "YYYY-MM-DD" or null, "source_text": string}
#   ]
# }

# HOW TO SPLIT (most important):
# - One task = ONE company + ONE category. Return one object per task.
# - A company with several different instructions -> one object per instruction, each with its own category.
# - One instruction that applies to several companies (e.g. "annual return for ABC, XYZ and DEF") -> one object per company.
# - Several companies, each with their own instructions -> keep each company's instructions with that company only. Never attach one company's instruction to another company.
# - One sentence with two distinct actions (e.g. "change of director and change of registered address") -> two tasks.
# - Instructions may be separated by numbers, bullets, dashes, commas, semicolons, "and", "also" or line breaks. Treat each as a possible separate task.
# - source_text = the words from the message that this task came from (copy them, a short phrase is fine).

# FIELD RULES:
# - company: write the name exactly as the message spells it. Do not add or remove "Sdn Bhd" or "Berhad". If it clearly refers to one of the known companies below, use that exact spelling. If the company is not clear for a task, use null.
# - category: must be copied exactly from the allowed list. If none fits, use null. Never invent a category.
# - date_received: the date the instruction was RECEIVED, as YYYY-MM-DD. Convert "today", "yesterday", "last Friday", "5 Nov" (use the current year if no year is given). A date that applies to the whole message applies to every task, unless a task has its own date. Deadlines and filing dates are NOT the received date. If no received date is stated, use null.
# - NEVER guess. If something is not stated or clearly implied, use null.

# INTENT: "update" if the message asks to change an existing task ("update ABC's ...", "change the category of ..."); "new_task" for new instructions; "unknown" if it is not a CoSec instruction (then tasks is []).

# Allowed categories:
# <<CATEGORIES>>

# Known companies:
# <<COMPANIES>>

# EXAMPLES

# Message: ABC Sdn Bhd - change director and update registered address. XYZ Berhad - annual return. Received today from Mr Tan.
# Output: {"intent": "new_task", "tasks": [
#  {"company": "ABC Sdn Bhd", "category": "Change of Directors", "date_received": "<<TODAY>>", "source_text": "change director"},
#  {"company": "ABC Sdn Bhd", "category": "Change of Registered Address", "date_received": "<<TODAY>>", "source_text": "update registered address"},
#  {"company": "XYZ Berhad", "category": "Annual Return", "date_received": "<<TODAY>>", "source_text": "annual return"}]}

# Message: Need annual return for Alpha Sdn Bhd and Beta Sdn Bhd, received 5 Nov
# Output: {"intent": "new_task", "tasks": [
#  {"company": "Alpha Sdn Bhd", "category": "Annual Return", "date_received": "<<YEAR>>-11-05", "source_text": "annual return for Alpha Sdn Bhd"},
#  {"company": "Beta Sdn Bhd", "category": "Annual Return", "date_received": "<<YEAR>>-11-05", "source_text": "annual return for Beta Sdn Bhd"}]}

# Message: Please do the KYC
# Output: {"intent": "new_task", "tasks": [
#  {"company": null, "category": "KYC / Client Due Diligence", "date_received": null, "source_text": "Please do the KYC"}]}
# """


# def _build_system(categories, companies, today):
#     return (
#         SYSTEM_TEMPLATE
#         .replace("<<TODAY>>", today)
#         .replace("<<YEAR>>", today[:4])
#         .replace("<<CATEGORIES>>", "\n".join(f"- {c}" for c in categories))
#         .replace("<<COMPANIES>>", "\n".join(f"- {c}" for c in companies) or "(none yet)")
#     )


# def _parse_json(text):
#     text = text.strip()
#     text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
#     start, end = text.find("{"), text.rfind("}")
#     if start == -1 or end == -1:
#         raise ValueError("No JSON found in AI response")
#     return json.loads(text[start:end + 1])


# def _text(value):
#     if value is None:
#         return None
#     value = str(value).strip()
#     return value or None


# def _valid_date(value):
#     value = _text(value)
#     if not value:
#         return None
#     try:
#         return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
#     except ValueError:
#         return None


# def _clean(result, categories):
#     """Check the AI's answer in code, so a bad value can never slip through."""
#     cat_lookup = {c.lower(): c for c in categories}
#     tasks = []
#     for t in result.get("tasks") or []:
#         company = _text(t.get("company"))
#         category = cat_lookup.get((_text(t.get("category")) or "").lower())  # must be in the list
#         date_received = _valid_date(t.get("date_received"))                  # must be a real date
#         missing = [name for name, value in
#                    (("company", company), ("category", category), ("date_received", date_received))
#                    if not value]
#         tasks.append({
#             "company": company,
#             "category": category,
#             "date_received": date_received,
#             "source_text": _text(t.get("source_text")) or "",
#             "missing": missing,
#         })
#     intent = result.get("intent")
#     if intent not in ("new_task", "update", "unknown"):
#         intent = "unknown"
#     return {"intent": intent, "tasks": tasks}


# def extract_tasks(message, categories, companies, today):
#     system = _build_system(categories, companies, today)
#     last_error = None
#     for _ in range(2):  # one retry if the AI's answer can't be read
#         response = client.messages.create(
#             model=MODEL,
#             max_tokens=4000,
#             system=system,
#             messages=[{"role": "user", "content": message}],
#         )
#         if response.stop_reason == "max_tokens":
#             raise ValueError("The message is too long to process in one go. Please split it into smaller parts.")
#         try:
#             return _clean(_parse_json(response.content[0].text), categories)
#         except ValueError as e:  # includes json.JSONDecodeError
#             last_error = e
#     raise ValueError(f"Could not read the AI's answer: {last_error}")

import json
import os
import re
from datetime import date, datetime, timedelta

import anthropic

_client = None


def _get_client():
    """Create the Claude client only when it is needed (demo mode never needs it)."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    return _client

MODEL = "claude-sonnet-5-5"

SYSTEM_TEMPLATE = """You turn messages from staff at a Malaysian corporate services firm into a list of Company Secretarial (CoSec) task records.

Today's date is <<TODAY>> (YYYY-MM-DD).

OUTPUT: only a JSON object. No explanation, no markdown fences.
{
  "intent": "new_task" | "update" | "unknown",
  "tasks": [
    {"company": string or null, "category": string or null, "date_received": "YYYY-MM-DD" or null, "source_text": string}
  ]
}

HOW TO SPLIT (most important):
- One task = ONE company + ONE category. Return one object per task.
- A company with several different instructions -> one object per instruction, each with its own category.
- One instruction that applies to several companies (e.g. "annual return for ABC, XYZ and DEF") -> one object per company.
- Several companies, each with their own instructions -> keep each company's instructions with that company only. Never attach one company's instruction to another company.
- One sentence with two distinct actions (e.g. "change of director and change of registered address") -> two tasks.
- Instructions may be separated by numbers, bullets, dashes, commas, semicolons, "and", "also" or line breaks. Treat each as a possible separate task.
- source_text = the words from the message that this task came from (copy them, a short phrase is fine).

FIELD RULES:
- company: write the name exactly as the message spells it. Do not add or remove "Sdn Bhd" or "Berhad". If it clearly refers to one of the known companies below, use that exact spelling. If the company is not clear for a task, use null.
- category: must be copied exactly from the allowed list. If none fits, use null. Never invent a category.
- date_received: the date the instruction was RECEIVED, as YYYY-MM-DD. Convert "today", "yesterday", "last Friday", "5 Nov" (use the current year if no year is given). A date that applies to the whole message applies to every task, unless a task has its own date. Deadlines and filing dates are NOT the received date. If no received date is stated, use null.
- NEVER guess. If something is not stated or clearly implied, use null.

INTENT: "update" if the message asks to change an existing task ("update ABC's ...", "change the category of ..."); "new_task" for new instructions; "unknown" if it is not a CoSec instruction (then tasks is []).

Allowed categories:
<<CATEGORIES>>

Known companies:
<<COMPANIES>>

EXAMPLES

Message: ABC Sdn Bhd - change director and update registered address. XYZ Berhad - annual return. Received today from Mr Tan.
Output: {"intent": "new_task", "tasks": [
 {"company": "ABC Sdn Bhd", "category": "Change of Directors", "date_received": "<<TODAY>>", "source_text": "change director"},
 {"company": "ABC Sdn Bhd", "category": "Change of Registered Address", "date_received": "<<TODAY>>", "source_text": "update registered address"},
 {"company": "XYZ Berhad", "category": "Annual Return", "date_received": "<<TODAY>>", "source_text": "annual return"}]}

Message: Need annual return for Alpha Sdn Bhd and Beta Sdn Bhd, received 5 Nov
Output: {"intent": "new_task", "tasks": [
 {"company": "Alpha Sdn Bhd", "category": "Annual Return", "date_received": "<<YEAR>>-11-05", "source_text": "annual return for Alpha Sdn Bhd"},
 {"company": "Beta Sdn Bhd", "category": "Annual Return", "date_received": "<<YEAR>>-11-05", "source_text": "annual return for Beta Sdn Bhd"}]}

Message: Please do the KYC
Output: {"intent": "new_task", "tasks": [
 {"company": null, "category": "KYC / Client Due Diligence", "date_received": null, "source_text": "Please do the KYC"}]}
"""


def _build_system(categories, companies, today):
    return (
        SYSTEM_TEMPLATE
        .replace("<<TODAY>>", today)
        .replace("<<YEAR>>", today[:4])
        .replace("<<CATEGORIES>>", "\n".join(f"- {c}" for c in categories))
        .replace("<<COMPANIES>>", "\n".join(f"- {c}" for c in companies) or "(none yet)")
    )


def _parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON found in AI response")
    return json.loads(text[start:end + 1])


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _valid_date(value):
    value = _text(value)
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _clean(result, categories):
    """Check the AI's answer in code, so a bad value can never slip through."""
    cat_lookup = {c.lower(): c for c in categories}
    tasks = []
    for t in result.get("tasks") or []:
        company = _text(t.get("company"))
        category = cat_lookup.get((_text(t.get("category")) or "").lower())  # must be in the list
        date_received = _valid_date(t.get("date_received"))                  # must be a real date
        missing = [name for name, value in
                   (("company", company), ("category", category), ("date_received", date_received))
                   if not value]
        tasks.append({
            "company": company,
            "category": category,
            "date_received": date_received,
            "source_text": _text(t.get("source_text")) or "",
            "missing": missing,
        })
    intent = result.get("intent")
    if intent not in ("new_task", "update", "unknown"):
        intent = "unknown"
    return {"intent": intent, "tasks": tasks}


# ======================================================================
# DEMO MODE - test the whole app WITHOUT the AI and WITHOUT an API key.
# A simple keyword matcher fills the table instead of Claude. It is only
# for testing the screen and the database, not for judging AI quality.
# ======================================================================
def demo_mode():
    """DEMO_MODE=true in .env forces demo; DEMO_MODE=false forces the real AI;
    if it is blank, demo is used whenever there is no real API key."""
    setting = os.getenv("DEMO_MODE", "").strip().lower()
    if setting in ("1", "true", "yes", "on"):
        return True
    if setting in ("0", "false", "no", "off"):
        return False
    return not os.getenv("ANTHROPIC_API_KEY", "").strip().startswith("sk-ant-")


# keyword -> category. Order matters: a matched phrase is blanked out so a later
# keyword cannot match the same words twice.
_KEYWORDS = [
    (r"shareholders?'?s?'?\s+resolution", "Shareholders' Resolutions"),
    (r"board\s+resolution|\bresolution", "Board Resolutions"),
    (r"incorporat", "Company Incorporation"),
    (r"annual\s+return", "Annual Return"),
    (r"financial\s+statement", "Financial Statements"),
    (r"director", "Change of Directors"),
    (r"share\s*holder", "Change of Shareholders"),
    (r"share\s+transfer|transfer\s+of\s+shares?", "Share Transfer"),
    (r"allot", "Share Allotment"),
    (r"company\s+name|change\s+(?:of\s+)?name|name\s+change", "Change of Company Name"),
    (r"registered\s+address", "Change of Registered Address"),
    (r"business\s+address", "Change of Business Address"),
    (r"constitution", "Company Constitution"),
    (r"beneficial\s+owner|\bbo\b", "Beneficial Ownership / BO Reporting"),
    (r"statutory\s+register", "Statutory Registers"),
    (r"\bcharges?\b", "Company Charges"),
    (r"\bkyc\b|due\s+diligence|\bcdd\b", "KYC / Client Due Diligence"),
    (r"compliance", "Compliance / Regulatory Matters"),
    (r"advisory", "Corporate Advisory"),
    (r"enquir", "General Enquiries"),
]

# Company names: capitalised words followed by Sdn Bhd / Berhad / Bhd / Pte Ltd / Ltd / LLP
_COMPANY = re.compile(
    r"((?:(?:[A-Z][\w'\u2019\-]*|&)\s+){1,5}(?i:sdn\s+bhd|berhad|bhd|pte\s+ltd|ltd|llp))(?![\w])"
)
_STOP_WORDS = {"please", "need", "needs", "hi", "hello", "dear", "update", "the", "for", "also",
               "and", "received", "kindly", "pls", "new", "urgent", "re", "change", "add", "file"}
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _clean_company(name):
    words = name.split()
    while len(words) > 2 and words[0].lower() in _STOP_WORDS:
        words.pop(0)
    return " ".join(words)


def _find_categories(text, categories):
    t, found = text.lower(), []
    for pattern, category in _KEYWORDS:
        m = re.search(pattern, t)
        if m and category in categories:
            found.append(category)
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    return found


def _find_date(text, today):
    t = text.lower()
    m = re.search(r"\b\d{4}-\d{2}-\d{2}\b", t)
    if m:
        return m.group(0)
    if "yesterday" in t:
        return (today - timedelta(days=1)).isoformat()
    if "today" in t:
        return today.isoformat()
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")[a-z]*(?:\s+(\d{4}))?", t)
    if m:
        try:
            return date(int(m.group(3) or today.year), _MONTHS.index(m.group(2)) + 1, int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def _demo_extract(message, categories, today_text):
    today = date.fromisoformat(today_text)
    text = re.sub(r"\b(Sdn|Pte)\.\s*(Bhd|Ltd)\b\.?", r"\1 \2", message, flags=re.I)
    segments = [s.strip(" -\u2022*\t") for s in re.split(r"(?<=[.!?;])\s+|\n+", text)]
    segments = [s for s in segments if s]

    tasks, current_companies, current_date = [], [], None
    for seg in segments:
        raw = _COMPANY.findall(seg)
        companies = [_clean_company(c) for c in raw]
        rest = seg
        for c in raw:
            rest = rest.replace(c, " ")
        seg_date = _find_date(seg, today)
        cats = _find_categories(rest, categories)
        if companies:
            current_companies = companies
        if seg_date:
            current_date = seg_date
        if not cats:
            continue
        for company in (companies or current_companies or [None]):
            for category in cats:
                tasks.append({"company": company, "category": category,
                              "date_received": seg_date or current_date, "source_text": seg})

    # a company was named but no category was found: still give the user a row to complete
    if not tasks and current_companies:
        tasks = [{"company": c, "category": None, "date_received": current_date,
                  "source_text": message[:80]} for c in current_companies]

    # one date in the whole message ("... Received today.") applies to every task without a date
    dates = {d for d in (_find_date(s, today) for s in segments) if d}
    if len(dates) == 1:
        only = next(iter(dates))
        for t in tasks:
            t["date_received"] = t["date_received"] or only

    intent = "update" if re.search(r"\bupdate\b[^.]*\btask\b", message, re.I) else "new_task"
    return {"intent": intent if tasks else "unknown", "tasks": tasks}


def extract_tasks(message, categories, companies, today):
    if demo_mode():
        return _clean(_demo_extract(message, categories, today), categories)
    system = _build_system(categories, companies, today)
    last_error = None
    for _ in range(2):  # one retry if the AI's answer can't be read
        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        if response.stop_reason == "max_tokens":
            raise ValueError("The message is too long to process in one go. Please split it into smaller parts.")
        try:
            return _clean(_parse_json(response.content[0].text), categories)
        except ValueError as e:  # includes json.JSONDecodeError
            last_error = e
    raise ValueError(f"Could not read the AI's answer: {last_error}")