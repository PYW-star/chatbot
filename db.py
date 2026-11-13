import os
import re
import json
import difflib
from contextlib import contextmanager
from datetime import date, datetime

import psycopg2
from psycopg2.extras import RealDictCursor, Json


# ---------- connection ----------
def _connect():
    """Connection details come from environment variables (see .env.example)."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "cosec_tasks"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
        options="-c timezone=Asia/Kuala_Lumpur",  # show times in Malaysia time
    )


@contextmanager
def get_cursor():
    """Open a connection, give a cursor, COMMIT if all went well, ROLLBACK if not."""
    conn = _connect()
    try:
        with conn:  # commit on success, rollback on any exception
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()


def check_connection():
    """Raises an error if the database cannot be reached."""
    with get_cursor() as cur:
        cur.execute("SELECT 1")


# ---------- reading ----------
def get_categories():
    with get_cursor() as cur:
        cur.execute("SELECT category_name FROM category ORDER BY category_id")
        return [r["category_name"] for r in cur.fetchall()]


def get_companies():
    with get_cursor() as cur:
        cur.execute("SELECT company_name FROM company ORDER BY company_name")
        return [r["company_name"] for r in cur.fetchall()]


def list_tasks(company=None):
    sql = """SELECT t.task_id, c.company_name AS company, t.date_received,
                    cat.category_name AS category, t.created_by, t.created_at
             FROM task t
             JOIN company c    ON c.company_id = t.company_id
             JOIN category cat ON cat.category_id = t.category_id"""
    params = []
    if company:
        sql += " WHERE c.company_name = %s"
        params.append(company)
    sql += " ORDER BY t.date_received DESC, t.task_id DESC"
    with get_cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def get_task(task_id):
    with get_cursor() as cur:
        cur.execute(
            """SELECT t.task_id, c.company_name AS company, cat.category_name AS category,
                      t.date_received, t.raw_message, t.created_by, t.created_at
               FROM task t
               JOIN company c      ON c.company_id = t.company_id
               JOIN category cat ON cat.category_id = t.category_id
               WHERE t.task_id = %s""",
            (task_id,),
        )
        return dict(cur.fetchone())


def get_audit(task_id):
    """Audit entries for one task, newest first."""
    with get_cursor() as cur:
        cur.execute(
            """SELECT audit_id, entry_no, action_type, old_value, new_value, audited_by, audited_at
               FROM audit_log WHERE task_id = %s
               ORDER BY entry_no DESC""",
            (task_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# ---------- company name matching ----------
def _norm(name):
    n = name.lower()
    n = re.sub(r"[.,]", "", n)
    n = re.sub(r"\b(sdn|bhd|berhad|pte|ltd|limited)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def match_company(name, threshold=0.85):
    """Return the existing company name that closely matches, else the name as typed."""
    if not name:
        return name
    best, best_score = None, 0.0
    for existing in get_companies():
        score = difflib.SequenceMatcher(None, _norm(name), _norm(existing)).ratio()
        if score > best_score:
            best, best_score = existing, score
    return best if best and best_score >= threshold else name


# ---------- writing ----------
def _to_date(value, field):
    if value in (None, ""):
        raise ValueError(f"'{field}' is required.")
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"'{field}' must be in YYYY-MM-DD format (got '{value}').")


def _get_or_create_company(cur, name):
    # If the company already exists (any capitalisation), the insert is skipped.
    cur.execute("INSERT INTO company (company_name) VALUES (%s) ON CONFLICT DO NOTHING", (name,))
    cur.execute("SELECT company_id FROM company WHERE lower(company_name) = lower(%s)", (name,))
    return cur.fetchone()["company_id"]


def _next_task_id(cur, date_received):
    """Build the next task ID for this received date, e.g. T261112001.
    The counter row is locked until the transaction ends, so two people saving
    at the same time can never get the same number."""
    cur.execute(
        """INSERT INTO task_counter (counter_date, last_no) VALUES (%s, 1)
           ON CONFLICT (counter_date)
           DO UPDATE SET last_no = task_counter.last_no + 1
           RETURNING last_no""",
        (date_received,),
    )
    n = cur.fetchone()["last_no"]
    if n > 999:
        raise ValueError(f"More than 999 tasks for {date_received}: task ID limit reached.")
    return f"T{date_received:%y%m%d}{n:03d}"


def add_audit(cur, task_id, action_type, old_value, new_value, user):
    """Add the next entry to this task's audit log (entry 1 = CREATE, then 2, 3 ...).
    The task row is locked first, so two people changing the same task at the same
    moment get separate, correctly numbered entries."""
    cur.execute("SELECT 1 FROM task WHERE task_id = %s FOR UPDATE", (task_id,))
    cur.execute("SELECT COALESCE(MAX(entry_no), 0) + 1 AS n FROM audit_log WHERE task_id = %s", (task_id,))
    n = cur.fetchone()["n"]
    dumps = lambda o: json.dumps(o, ensure_ascii=False, default=str)
    cur.execute(
        """INSERT INTO audit_log (task_id, entry_no, action_type, old_value, new_value, audited_by)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (task_id, n, action_type,
         Json(old_value, dumps=dumps) if old_value is not None else None,
         Json(new_value, dumps=dumps), user),
    )
    return n


def _insert_one(cur, task, raw_message, user):
    company_name = (task.get("company") or "").strip()
    if not company_name:
        raise ValueError("Company is required.")
    category_name = (task.get("category") or "").strip()
    if not category_name:
        raise ValueError(f"Category is required (company: {company_name}).")
    date_received = _to_date(task.get("date_received"), "date_received")

    cur.execute("SELECT category_id FROM category WHERE category_name = %s", (category_name,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Unknown category '{category_name}'. Pick one from the list.")
    category_id = row["category_id"]

    company_id = _get_or_create_company(cur, company_name)
    task_id = _next_task_id(cur, date_received)
    cur.execute(
        """INSERT INTO task (task_id, company_id, category_id, date_received, raw_message, created_by)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (task_id, company_id, category_id, date_received, raw_message, user),
    )

    snapshot = {"company": company_name, "category": category_name,
                "date_received": date_received}
    add_audit(cur, task_id, "CREATE", None, snapshot, user)
    return task_id


def insert_tasks(tasks, raw_message, user):
    """Save several tasks in ONE transaction: either all are saved or none are."""
    with get_cursor() as cur:
        return [_insert_one(cur, t, raw_message, user) for t in tasks]