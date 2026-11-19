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
FILE = Path(os.getenv("COSEC_EXCEL_PATH", str(ROOT / "CoSec_Task_Management.xlsx"))).expanduser().resolve()
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

# for database:

#   import os
# import re
# import json
# import difflib
# from contextlib import contextmanager
# from datetime import date, datetime

# import psycopg2
# from psycopg2.extras import RealDictCursor, Json


# # ---------- connection ----------
# def _connect():
#     """Connection details come from environment variables (see .env.example)."""
#     return psycopg2.connect(
#         host=os.getenv("DB_HOST", "localhost"),
#         port=os.getenv("DB_PORT", "5432"),
#         dbname=os.getenv("DB_NAME", "cosec_tasks"),
#         user=os.environ["DB_USER"],
#         password=os.environ["DB_PASSWORD"],
#         sslmode=os.getenv("DB_SSLMODE", "prefer"),  # hosted databases (e.g. Neon) need "require"
#         connect_timeout=10,                          # a sleeping hosted database can take a few seconds to wake
#     )


# @contextmanager
# def get_cursor():
#     """Open a connection, give a cursor, COMMIT if all went well, ROLLBACK if not."""
#     conn = _connect()
#     try:
#         with conn:  # commit on success, rollback on any exception
#             with conn.cursor(cursor_factory=RealDictCursor) as cur:
#                 cur.execute("SET LOCAL TIME ZONE 'Asia/Kuala_Lumpur'")  # show times in Malaysia time
#                 yield cur
#     finally:
#         conn.close()


# def check_connection():
#     """Raises an error if the database cannot be reached."""
#     with get_cursor() as cur:
#         cur.execute("SELECT 1")


# # ---------- reading ----------
# def get_categories():
#     with get_cursor() as cur:
#         cur.execute("SELECT category_name FROM category ORDER BY category_id")
#         return [r["category_name"] for r in cur.fetchall()]


# def get_companies():
#     with get_cursor() as cur:
#         cur.execute("SELECT company_name FROM company ORDER BY company_name")
#         return [r["company_name"] for r in cur.fetchall()]


# def list_tasks(company=None):
#     sql = """SELECT t.task_id, c.company_name AS company, t.date_received,
#                     cat.category_name AS category, t.created_by, t.created_at
#              FROM task t
#              JOIN company c    ON c.company_id = t.company_id
#              JOIN category cat ON cat.category_id = t.category_id"""
#     params = []
#     if company:
#         sql += " WHERE c.company_name = %s"
#         params.append(company)
#     sql += " ORDER BY t.date_received DESC, t.task_id DESC"
#     with get_cursor() as cur:
#         cur.execute(sql, params)
#         return [dict(r) for r in cur.fetchall()]


# def get_task(task_id):
#     with get_cursor() as cur:
#         cur.execute(
#             """SELECT t.task_id, c.company_name AS company, cat.category_name AS category,
#                       t.date_received, t.raw_message, t.created_by, t.created_at
#                FROM task t
#                JOIN company c      ON c.company_id = t.company_id
#                JOIN category cat ON cat.category_id = t.category_id
#                WHERE t.task_id = %s""",
#             (task_id,),
#         )
#         return dict(cur.fetchone())


# def get_audit(task_id):
#     """Audit entries for one task, newest first."""
#     with get_cursor() as cur:
#         cur.execute(
#             """SELECT audit_id, entry_no, action_type, old_value, new_value, audited_by, audited_at
#                FROM audit_log WHERE task_id = %s
#                ORDER BY entry_no DESC""",
#             (task_id,),
#         )
#         return [dict(r) for r in cur.fetchall()]


# def match_company(name, threshold=0.85, existing=None):
#     """Return the saved company name that closely matches, else the name as typed.
#     `existing` lets a test pass its own list instead of reading the database."""
#     if not name:
#         return name
#     best, best_score = None, 0.0
#     for candidate in (existing if existing is not None else get_companies()):
#         score = difflib.SequenceMatcher(None, _norm(name), _norm(candidate)).ratio()
#         if score > best_score:
#             best, best_score = candidate, score
#     return best if best and best_score >= threshold else name


# # ---------- writing ----------
# def _to_date(value, field):
#     if value in (None, ""):
#         raise ValueError(f"'{field}' is required.")
#     if isinstance(value, date):
#         return value
#     try:
#         return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
#     except ValueError:
#         raise ValueError(f"'{field}' must be in YYYY-MM-DD format (got '{value}').")


# def _get_or_create_company(cur, name):
#     # If the company already exists (any capitalisation), the insert is skipped.
#     cur.execute("INSERT INTO company (company_name) VALUES (%s) ON CONFLICT DO NOTHING", (name,))
#     cur.execute("SELECT company_id FROM company WHERE lower(company_name) = lower(%s)", (name,))
#     return cur.fetchone()["company_id"]


# def _next_task_id(cur, date_received):
#     """Build the next task ID for this received date, e.g. T261112001.
#     The counter row is locked until the transaction ends, so two people saving
#     at the same time can never get the same number."""
#     cur.execute(
#         """INSERT INTO task_counter (counter_date, last_no) VALUES (%s, 1)
#            ON CONFLICT (counter_date)
#            DO UPDATE SET last_no = task_counter.last_no + 1
#            RETURNING last_no""",
#         (date_received,),
#     )
#     n = cur.fetchone()["last_no"]
#     if n > 999:
#         raise ValueError(f"More than 999 tasks for {date_received}: task ID limit reached.")
#     return f"T{date_received:%y%m%d}{n:03d}"


# def add_audit(cur, task_id, action_type, old_value, new_value, user):
#     """Add the next entry to this task's audit log (entry 1 = CREATE, then 2, 3 ...).
#     The task row is locked first, so two people changing the same task at the same
#     moment get separate, correctly numbered entries."""
#     cur.execute("SELECT 1 FROM task WHERE task_id = %s FOR UPDATE", (task_id,))
#     cur.execute("SELECT COALESCE(MAX(entry_no), 0) + 1 AS n FROM audit_log WHERE task_id = %s", (task_id,))
#     n = cur.fetchone()["n"]
#     dumps = lambda o: json.dumps(o, ensure_ascii=False, default=str)
#     cur.execute(
#         """INSERT INTO audit_log (task_id, entry_no, action_type, old_value, new_value, audited_by)
#            VALUES (%s, %s, %s, %s, %s, %s)""",
#         (task_id, n, action_type,
#          Json(old_value, dumps=dumps) if old_value is not None else None,
#          Json(new_value, dumps=dumps), user),
#     )
#     return n


# def _insert_one(cur, task, raw_message, user):
#     company_name = (task.get("company") or "").strip()
#     if not company_name:
#         raise ValueError("Company is required.")
#     category_name = (task.get("category") or "").strip()
#     if not category_name:
#         raise ValueError(f"Category is required (company: {company_name}).")
#     date_received = _to_date(task.get("date_received"), "date_received")

#     cur.execute("SELECT category_id FROM category WHERE category_name = %s", (category_name,))
#     row = cur.fetchone()
#     if not row:
#         raise ValueError(f"Unknown category '{category_name}'. Pick one from the list.")
#     category_id = row["category_id"]

#     company_id = _get_or_create_company(cur, company_name)
#     task_id = _next_task_id(cur, date_received)
#     cur.execute(
#         """INSERT INTO task (task_id, company_id, category_id, date_received, raw_message, created_by)
#            VALUES (%s, %s, %s, %s, %s, %s)""",
#         (task_id, company_id, category_id, date_received, raw_message, user),
#     )

#     snapshot = {"company": company_name, "category": category_name,
#                 "date_received": date_received}
#     add_audit(cur, task_id, "CREATE", None, snapshot, user)
#     return task_id


# def insert_tasks(tasks, raw_message, user):
#     """Save several tasks in ONE transaction: either all are saved or none are."""
#     with get_cursor() as cur:
#         return [_insert_one(cur, t, raw_message, user) for t in tasks]