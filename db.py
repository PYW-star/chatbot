"""Local Excel storage for the original CoSec app (no SQL server required)."""
import os
import re
import json
import difflib
import tempfile
import shutil
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from filelock import FileLock
from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parent
FILE = Path(os.getenv("COSEC_EXCEL_PATH", str(ROOT / "CoSec_Task_Management_Sheet.xlsx"))).expanduser().resolve()
SHEETS = {
    "Companies": ["company_id", "company_name", "added_at"],
    "Categories": ["category_id", "category_name", "category_desc"],
    "Tasks": ["task_id", "company_id", "category_id", "date_received", "raw_message", "created_by", "created_at", "fee_amount"],
    "Task_Counter": ["counter_date", "last_no"],
    "Audit_Log": ["task_id", "audit_id", "entry_no", "action_type", "old_value", "new_value", "audited_by", "audited_at"],
}
DEFAULT_CATEGORIES = [
    "Company Incorporation", "Annual Return", "Financial Statements", "Change of Directors",
    "Change of Shareholders", "Share Transfer", "Share Allotment", "Change of Company Name",
    "Change of Registered Address", "Change of Business Address", "Company Constitution",
    "Board Resolutions", "Shareholders' Resolutions", "Beneficial Ownership / BO Reporting",
    "Company Charges", "Statutory Registers", "KYC / Client Due Diligence",
    "Compliance / Regulatory Matters", "Corporate Advisory", "General Enquiries", "Others",
]

def _safe(value):
    # Avoid Excel interpreting untrusted message text as a formula or DDE link.
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value

def _rows(ws):
    rows = list(ws.values)
    if not rows:
        return []
    return [dict(zip(rows[0], row)) for row in rows[1:] if any(v is not None for v in row)]

def _new_book():
    wb = Workbook()
    wb.remove(wb.active)
    for name, headers in SHEETS.items():
        ws = wb.create_sheet(name)
        ws.append(headers)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{ws.cell(1,len(headers)).column_letter}1"
    for i, name in enumerate(DEFAULT_CATEGORIES, 1):
        wb["Categories"].append([i, name, None])
    return wb

def _save(wb):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(suffix=".xlsx", dir=FILE.parent)
    os.close(fd)
    try:
        wb.save(temp)
        os.replace(temp, FILE)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def check_connection():
    """Validate the local Excel file, creating it on first run."""
    with FileLock(str(FILE) + ".lock", timeout=15):
        if not FILE.exists():
            _save(_new_book())
        wb = load_workbook(FILE, read_only=True, data_only=True)
        try:
            for name, headers in SHEETS.items():
                if name not in wb.sheetnames:
                    raise ValueError(f"Missing Excel sheet {name}. Back up and restore the workbook.")
                actual = [cell.value for cell in next(wb[name].iter_rows(min_row=1,max_row=1))]
                if actual != headers:
                    # Upgrade old Excel workbooks by adding the optional fee column.
                    if name == "Tasks" and actual == headers[:-1]:
                        wb.close()
                        mutable = load_workbook(FILE)
                        mutable["Tasks"].cell(1, len(headers), "fee_amount")
                        _save(mutable)
                        mutable.close()
                        wb = load_workbook(FILE, read_only=True, data_only=True)
                    else:
                        raise ValueError(f"Unexpected columns in {name}; expected {headers}.")
        finally:
            wb.close()
    return True

@contextmanager
def _book(write=False):
    check_connection()
    # This lock serializes writes and avoids simultaneous reads of an incomplete file.
    with FileLock(str(FILE) + ".lock", timeout=15):
        wb = load_workbook(FILE)
        try:
            yield wb
            if write:
                _save(wb)
        finally:
            wb.close()

def get_categories():
    with _book() as wb:
        return [r["category_name"] for r in _rows(wb["Categories"])]

def get_companies():
    with _book() as wb:
        return sorted([r["company_name"] for r in _rows(wb["Companies"])], key=str.lower)

# ---------- company name matching ----------
def _norm(name):
    n = name.lower()
    n = re.sub(r"[.,]", "", n)
    n = re.sub(r"\b(sdn|bhd|berhad|pte|ltd|limited)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()

def match_company(name, threshold=0.85):
    if not name:
        return name
    best, score = None, 0.0
    for existing in get_companies():
        s = difflib.SequenceMatcher(None, _norm(name), _norm(existing)).ratio()
        if s > score:
            best, score = existing, s
    return best if best and score >= threshold else name

def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])

def _timestamp(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))

def list_tasks(company=None):
    with _book() as wb:
        companies = {r["company_id"]: r["company_name"] for r in _rows(wb["Companies"])}
        categories = {r["category_id"]: r["category_name"] for r in _rows(wb["Categories"])}
        records = []
        for r in _rows(wb["Tasks"]):
            name = companies.get(r["company_id"])
            if company and name != company:
                continue
            records.append({"task_id":r["task_id"], "company":name, "date_received":_date(r["date_received"]),
                            "category":categories.get(r["category_id"]), "created_by":r["created_by"],
                            "created_at":_timestamp(r["created_at"]), "fee_amount":r.get("fee_amount")})
        return sorted(records, key=lambda r: (r["date_received"],r["task_id"]), reverse=True)

def get_task(task_id):
    with _book() as wb:
        companies = {r["company_id"]: r["company_name"] for r in _rows(wb["Companies"])}
        categories = {r["category_id"]: r["category_name"] for r in _rows(wb["Categories"])}
        for r in _rows(wb["Tasks"]):
            if r["task_id"] == task_id:
                return {"task_id":task_id, "company":companies[r["company_id"]],
                        "category":categories[r["category_id"]], "date_received":_date(r["date_received"]),
                        "raw_message":r["raw_message"], "created_by":r["created_by"],
                        "created_at":_timestamp(r["created_at"]), "fee_amount":r.get("fee_amount")}
    raise ValueError(f"Task {task_id} was not found")

def get_audit(task_id):
    with _book() as wb:
        result = []
        for r in _rows(wb["Audit_Log"]):
            if r["task_id"] == task_id:
                result.append({"audit_id":r["audit_id"], "entry_no":int(r["entry_no"]),
                               "action_type":r["action_type"],
                               "old_value":json.loads(r["old_value"]) if r["old_value"] else None,
                               "new_value":json.loads(r["new_value"]), "audited_by":r["audited_by"],
                               "audited_at":_timestamp(r["audited_at"])})
        return sorted(result, key=lambda r:r["entry_no"], reverse=True)

def _to_date(value, field):
    if value in (None, ""):
        raise ValueError(f"'{field}' is required.")
    try:
        return _date(value)
    except (ValueError, TypeError):
        raise ValueError(f"'{field}' must be in YYYY-MM-DD format (got '{value}').")

def _optional_fee(value):
    """A missing fee is unknown (None), not zero. Amounts use two decimal places."""
    from decimal import Decimal, InvalidOperation
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError("Fee must be a valid non-negative amount or blank.")
    cleaned = str(value).strip().replace(",", "")
    cleaned = re.sub(r"^(?:RM|MYR)\s*", "", cleaned, flags=re.I)
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Invalid fee '{value}'; enter an amount or leave it blank.")
    if not number.is_finite() or number < 0 or number.as_tuple().exponent < -2:
        raise ValueError("Fee must be non-negative with at most two decimal places, or blank.")
    return float(number)


def insert_tasks(tasks, raw_message, user):
    """Save all tasks atomically; validation failure leaves workbook unchanged."""
    if not str(user).strip():
        raise ValueError("Uploader name is required.")
    with _book(write=True) as wb:
        cats = {str(r["category_name"]).casefold():r for r in _rows(wb["Categories"])}
        existing_companies = {str(r["company_name"]).casefold():r for r in _rows(wb["Companies"])}
        counters = {str(r["counter_date"])[:10]:int(r["last_no"]) for r in _rows(wb["Task_Counter"])}
        new_companies, created = {}, []
        staged = []
        for t in tasks:
            name = str(t.get("company") or "").strip()
            category = str(t.get("category") or "").strip()
            if not name:
                raise ValueError("Company is required.")
            if not category:
                raise ValueError(f"Category is required (company: {name}).")
            cat = cats.get(category.casefold())
            if not cat:
                raise ValueError(f"Unknown category '{category}'. Pick one from the list.")
            received = _to_date(t.get("date_received"), "date_received")
            fee_amount = _optional_fee(t.get("fee_amount"))
            key = received.isoformat()
            next_no = counters.get(key,0)+1
            if next_no > 999:
                raise ValueError(f"More than 999 tasks for {key}: task ID limit reached.")
            counters[key] = next_no
            comp = existing_companies.get(name.casefold()) or new_companies.get(name.casefold())
            if comp is None:
                # Original app automatically registers a company when a task is saved.
                next_company_id = len(existing_companies)+len(new_companies)+1
                # Use max ID to preserve uniqueness if users removed spreadsheet rows.
                ids = [int(r["company_id"]) for r in list(existing_companies.values())+list(new_companies.values())]
                next_company_id = max(ids,default=0)+1
                comp = {"company_id":next_company_id,"company_name":name}
                new_companies[name.casefold()] = comp
            tid = f"T{received:%y%m%d}{next_no:03d}"
            created.append(tid)
            staged.append((tid,comp,cat,received,fee_amount))
        now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).replace(tzinfo=None)
        for comp in new_companies.values():
            wb["Companies"].append([comp["company_id"], _safe(comp["company_name"]), now])
        for tid,comp,cat,received,fee_amount in staged:
            wb["Tasks"].append([tid, comp["company_id"], cat["category_id"], received,
                                _safe(raw_message), _safe(user.strip()), now, fee_amount])
            wb["Tasks"].cell(wb["Tasks"].max_row, 8).number_format = '"RM "#,##0.00' 
            snapshot = {"company":comp["company_name"], "category":cat["category_name"],
                        "date_received":received.isoformat(), "fee_amount":fee_amount}
            wb["Audit_Log"].append([tid,"A"+tid[1:],1,"CREATE",None,
                                    json.dumps(snapshot,ensure_ascii=False),_safe(user.strip()),now])
        # Rewrite counter sheet in memory; no disk change until all stages succeed.
        ws=wb["Task_Counter"]
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row-1)
        for d,n in sorted(counters.items()):
            ws.append([d,n])
        return created
