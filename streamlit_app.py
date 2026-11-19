from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(override=True)  # reads COSEC_EXCEL_PATH and ANTHROPIC_API_KEY if configured

import pandas as pd
import re
import streamlit as st

import db
import extract

st.set_page_config(page_title="CoSec Task Log", layout="wide")

# Stop early with a clear message if the workbook cannot be opened.
try:
    db.check_connection()
except Exception as e:
    st.error(
        "Cannot open the local Excel workbook. Check that the file is not open in Excel and that its folder is writable. "
        f"\n\nDetails: {e}"
    )
    st.stop()

FIELDS = ["company", "category", "date_received", "fee_amount"]
COLUMNS = FIELDS + ["source_text"]   # source_text is only shown, never saved


def clean(value):
    """Turn blank/None/NaN cell values into None, otherwise a trimmed string."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip() or None


LABELS = {"company": "Company", "category": "Category", "date_received": "Date received", "fee_amount": "Fee (RM)", "status": "Status", "update_note": "Update note"}
ACTION_STYLE = {
    "CREATE": ":green-background[ CREATE ]",
    "UPDATE": ":orange-background[ UPDATE ]",
    "DELETE": ":red-background[ DELETE ]",
}


def esc(value):
    """Stop user text from being read as markdown formatting."""
    out = str(value)
    for ch in "\\*_[]~`":
        out = out.replace(ch, "\\" + ch)
    return out


def show_changes(old, new):
    old, new = old or {}, new or {}
    keys = [k for k in LABELS if k in old or k in new]
    keys += [k for k in sorted(old.keys() | new.keys()) if k not in LABELS]
    for k in keys:
        label = LABELS.get(k, k)
        if k in old and k in new and old[k] != new[k]:
            st.markdown(f"- **{label}:** :red[~~{esc(old[k])}~~] → :green[**{esc(new[k])}**]")
        elif k in new:
            st.markdown(f"- **{label}:** {esc(new[k])}")


def show_task(task_id):
    task = db.get_task(task_id)
    with st.container(border=True):
        st.markdown(f"#### `{task['task_id']}`")
        c1, c2, c3, c4 = st.columns(4)
        for col, title, val in [
            (c1, "Company", task["company"]),
            (c2, "Category", task["category"]),
            (c3, "Date received", f"{task['date_received']:%d %b %Y}"),
            (c4, "Uploaded by", task["created_by"]),
        ]:
            col.caption(title)
            col.markdown(f"**{esc(val)}**")
        st.caption(f"Status: {task.get('status', 'Pending')}")
        col_fee, = st.columns(1)
        col_fee.caption("Fee (RM)")
        fee = task.get("fee_amount")
        col_fee.markdown(f"**{'Not specified' if fee is None else f'RM {fee:,.2f}'}**")
        with st.expander("Original message"):
            st.text(task["raw_message"])

    entries = db.get_audit(task_id)
    audit_id = entries[0]["audit_id"] if entries else "A" + task_id[1:]
    st.markdown(f"##### Audit log `{audit_id}`")
    for e in entries:
        with st.container(border=True):
            left, right = st.columns([1, 6])
            left.markdown(ACTION_STYLE.get(e["action_type"], esc(e["action_type"])))
            left.caption(f"Entry {e['entry_no']}")
            right.markdown(f"**{esc(e['audited_by'])}** · {e['audited_at']:%d %b %Y, %I:%M %p}")
            show_changes(e["old_value"], e["new_value"])


# ---------- session state ----------
st.session_state.setdefault("chat", [])
st.session_state.setdefault("pending", None)      # extracted tasks awaiting confirmation
st.session_state.setdefault("pending_raw", "")
st.session_state.setdefault("pending_id", 0)

# ---------- sidebar ----------
st.sidebar.title("CoSec Task Log")
st.sidebar.caption(f"Local Excel: {db.FILE}")
user = st.sidebar.text_input("Your name (saved as 'uploaded by')")
if extract.demo_mode():
    st.sidebar.warning(
        "DEMO MODE: no AI is used. A simple keyword matcher fills the table, so write company "
        "names with capital letters (e.g. ABC Sdn Bhd). To use Claude, put a real "
        "ANTHROPIC_API_KEY in .env and set DEMO_MODE=false."
    )

tab_chat, tab_update, tab_records = st.tabs(["Add Tasks", "Update Tasks", "Records"])

# ---------- chatbox ----------
with tab_chat:
    for role, text in st.session_state.chat:
        with st.chat_message(role):
            st.write(text)

    message = st.chat_input("Type or paste a CoSec instruction...")

    if message:
        st.session_state.chat.append(("user", message))
        try:
            result = extract.extract_tasks(
                message, db.get_categories(), db.get_companies(), datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date().isoformat()
            )
        except Exception as e:
            st.session_state.chat.append(("assistant", f"Sorry, extraction failed: {e}"))
            st.session_state.pending = None
            st.rerun()

        tasks = result.get("tasks", [])
        if result.get("intent") == "unknown" or not tasks:
            st.session_state.chat.append(
                ("assistant", "I couldn't find a CoSec task in that message.")
            )
            st.session_state.pending = None
        else:
            if result.get("intent") == "update":
                st.session_state.chat.append(
                    ("assistant", "This looks like an update to an existing task. "
                                  "Updates are not built yet. Do not save this as a new task unless it is genuinely new.")
                )
            for t in tasks:
                # Do not automatically merge fuzzy matches of legally distinct entities.
                candidate = db.match_company(t.get("company"))
                if candidate and t.get("company") and candidate.casefold() == t["company"].casefold():
                    t["company"] = candidate
            st.session_state.pending = tasks
            st.session_state.pending_raw = message
            st.session_state.pending_id += 1
            counts = {}
            for t in tasks:
                name = t.get("company") or "(company not found)"
                counts[name] = counts.get(name, 0) + 1
            summary = ", ".join(f"{name} ({n})" for name, n in counts.items())
            noun = "company" if len(counts) == 1 else "companies"
            st.session_state.chat.append(
                ("assistant", f"I found {len(tasks)} task(s) for {len(counts)} {noun}: {summary}. "
                              "Please check below, edit if needed, then save.")
            )
        st.rerun()

    # ---------- confirmation card ----------
    if st.session_state.pending:
        st.subheader("Review before saving")
        tasks = st.session_state.pending

        missing = sorted({m for t in tasks for m in t.get("missing", [])})
        if missing:
            st.warning("Could not find: " + ", ".join(missing) + ". Please fill in or confirm.")

        df = pd.DataFrame(tasks).reindex(columns=COLUMNS)
        for i, task in enumerate(tasks):
            if not df.at[i, "category"] and task.get("suggested_category"):
                df.at[i, "category"] = task["suggested_category"]
        df = df.astype(object).where(df.notna(), "")

        st.caption("Date Received must be YYYY-MM-DD. It means when the instruction arrived, NOT its deadline. If missing, check the original email and enter the correct date before saving.")
        st.caption("Fee (RM) is optional. Leave it blank if the amount is unknown; 0 means explicitly no fee.")

        edited = st.data_editor(
            df,
            key=f"editor_{st.session_state.pending_id}",
            num_rows="dynamic",
            disabled=["source_text"],
            column_config={
                "company": st.column_config.TextColumn(
                    "Company Name"
                ),
                "date_received": st.column_config.TextColumn(
                    "Date Received",
                ),
                "source_text": st.column_config.TextColumn(
                    "Original Message"
                ),
                "fee_amount": st.column_config.NumberColumn(
                    "Fee (RM)",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    required=False
                ),
                "category": st.column_config.TextColumn(
                    "Task Category (editable — use existing or suggest a new one)",
                ),
            },
        )


        # An AI fallback to Others must always prompt for a human choice.
        # Keep this distinct from suggesting a genuinely unrecognised category.
        current_rows = edited.to_dict("records")
        unresolved_others = []
        for i, row in enumerate(current_rows):
            if str(row.get("category") or "").strip().casefold() != "others":
                continue
            suggestion = tasks[i].get("suggested_category") if i < len(tasks) else None
            st.warning(f"⚠️ Row {i+1}: The AI selected 'Others'. Would you like to add a new task category instead?")
            choice = st.radio(
                f"Row {i+1} — What category should this task use?",
                ["Please choose", "Keep Others", "Add new category"],
                key=f"others_choice_{st.session_state.pending_id}_{i}",
                horizontal=True,
            )
            if choice == "Add new category":
                proposed = st.text_input(
                    f"New category name for row {i+1}",
                    value=suggestion or "",
                    key=f"others_name_{st.session_state.pending_id}_{i}",
                    help="Choose a descriptive category name. It will still require explicit approval before saving.",
                ).strip()
                if proposed and proposed.casefold() != "others":
                    row["category"] = proposed
                else:
                    unresolved_others.append(i+1)
            elif choice == "Please choose":
                unresolved_others.append(i+1)

        # Warn before saving, using the confirmed selection, not only the AI's guess.
        approved_companies = db.get_companies()
        approved_categories = db.get_categories()
        canonical = lambda v: re.sub(r"[^a-z0-9]", "", str(v).casefold())
        company_lookup = {canonical(c): c for c in approved_companies}
        category_lookup = {c.casefold(): c for c in approved_categories}
        unknown_companies = sorted({str(r.get("company")).strip() for r in current_rows
                                    if clean(r.get("company")) and canonical(r["company"]) not in company_lookup})
        unknown_categories = sorted({str(r.get("category")).strip() for r in current_rows
                                     if clean(r.get("category")) and str(r["category"]).strip().casefold() not in category_lookup})
        if unknown_companies:
            st.warning("⚠️ New / unrecognised company names: " + "; ".join(unknown_companies) +
                       ". Verify spelling and legal entity before choosing to add.")
        if unknown_categories:
            st.warning("⚠️ New / unrecognised task categories: " + "; ".join(unknown_categories) +
                       ". Check whether an existing category fits before adding a new one.")
        allow_companies = st.checkbox("Yes, add the unrecognised company name(s) to the Companies list", value=False,
                                      disabled=not bool(unknown_companies), key=f"approve_companies_{st.session_state.pending_id}")
        allow_categories = st.checkbox("Yes, add the proposed new task category/category names to Categories", value=False,
                                       disabled=not bool(unknown_categories), key=f"approve_categories_{st.session_state.pending_id}")
        st.caption("Approval here is by the person recording the task. It is not owner-role authentication.")

        col1, col2 = st.columns(2)
        if col1.button("Save to Excel", type="primary"):
            if not user.strip():
                st.error("Enter your name in the sidebar first (saved as 'uploaded by').")
            else:
                rows = []
                for r in current_rows:
                    item = {k: clean(v) for k, v in r.items() if k != "fee_amount"}
                    if item.get("company") and canonical(item["company"]) in company_lookup:
                        item["company"] = company_lookup[canonical(item["company"])]
                    fee = r.get("fee_amount")
                    item["fee_amount"] = None if fee is None or pd.isna(fee) or str(fee).strip() == "" else fee
                    rows.append(item)
                bad = [i + 1 for i, r in enumerate(rows)
                       if not (r.get("company") and r.get("category") and r.get("date_received"))]
                if unresolved_others:
                    st.error(f"Please decide whether to keep 'Others' or add a new category for row(s) {unresolved_others}.")
                elif bad:
                    st.error(f"Row(s) {bad} are missing the company, category or date received.")
                elif unknown_companies and not allow_companies:
                    st.error("Review and approve the new companies, or correct their names before saving.")
                elif unknown_categories and not allow_categories:
                    st.error("Review and approve the new categories, or use an existing category before saving.")
                else:
                    try:
                        saved_ids = db.insert_tasks(rows, st.session_state.pending_raw, user.strip(),
                                                    approve_new_companies=allow_companies,
                                                    approve_new_categories=allow_categories)
                    except ValueError as e:
                        st.error(str(e))          # e.g. a date typed in the wrong format
                    except Exception as e:
                        st.error(f"Could not save: {e}")
                    else:
                        st.session_state.pending = None
                        st.session_state.chat.append(
                            ("assistant", f"Saved {len(saved_ids)} task(s): " + ", ".join(saved_ids))
                        )
                        st.rerun()
        if col2.button("Discard"):
            st.session_state.pending = None
            st.rerun()

# ---------- update an existing task ----------
with tab_update:
    st.subheader("Update an existing task")
    st.caption("Search by task ID, company, or category. Any employee can update a task. Changes are saved to Excel and recorded in the audit log.")
    task_options = db.list_tasks()
    if not task_options:
        st.info("There are no tasks to update yet. Add a task first.")
    else:
        lookup = {r["task_id"]: r for r in task_options}
        selected_id = st.selectbox(
            "Search for a task",
            options=list(lookup),
            format_func=lambda tid: f"{tid}  ·  {lookup[tid]['company']}  ·  {lookup[tid]['category']}  ·  {lookup[tid]['status']}",
            index=None,
            placeholder="Type task ID, company, or category...",
            key="update_task_selection",
        )
        if selected_id:
            current = db.get_task(selected_id)
            # Store the initial snapshot until the user switches task or saves.
            if st.session_state.get("update_snapshot_id") != selected_id:
                st.session_state.update_snapshot_id = selected_id
                st.session_state.update_snapshot = {k: current[k] for k in ("company", "category", "date_received", "fee_amount", "status")}
            snapshot = st.session_state.update_snapshot
            st.caption(f"Task ID: {selected_id} · Created by {current['created_by']} on {current['created_at']:%d %b %Y}")
            with st.expander("Original instruction"):
                st.text(current["raw_message"])
            companies = db.get_companies()
            categories = db.get_categories()
            with st.form(f"task_update_form_{selected_id}"):
                left, right = st.columns(2)
                with left:
                    status = st.selectbox("Status", db.TASK_STATUSES, index=db.TASK_STATUSES.index(snapshot["status"]))
                    company = st.selectbox("Company", companies, index=companies.index(snapshot["company"]))
                    date_received = st.date_input("Date received (not deadline)", value=snapshot["date_received"])
                with right:
                    category = st.selectbox("Task category", categories, index=categories.index(snapshot["category"]))
                    original_fee = snapshot["fee_amount"]
                    fee_value = st.text_input("Fee (RM) — blank if unknown", value="" if original_fee is None else str(original_fee))
                    note = st.text_area("Update note (optional)", placeholder="E.g. Signed documents received; preparing SSM filing", max_chars=2000)
                submitted = st.form_submit_button("Save update to Excel", type="primary")
            if submitted:
                if not user.strip():
                    st.error("Enter your name in the sidebar before updating.")
                else:
                    try:
                        entry = db.update_task(
                            selected_id,
                            {"status": status, "company": company, "category": category,
                             "date_received": date_received, "fee_amount": fee_value},
                            user.strip(), note=note, expected=snapshot,
                        )
                    except Exception as exc:
                        st.error(f"Could not update task: {exc}")
                    else:
                        st.success(f"Task {selected_id} updated. Audit entry #{entry} saved.")
                        st.session_state.pop("update_snapshot_id", None)
                        st.session_state.pop("update_snapshot", None)
                        st.rerun()
            with st.expander("View audit history for this task"):
                for event in db.get_audit(selected_id):
                    st.markdown(f"**{event['action_type']}** · {event['audited_by']} · {event['audited_at']:%d %b %Y, %I:%M %p}")
                    show_changes(event["old_value"], event["new_value"])

# ---------- records ----------

with tab_records:
    companies = db.get_companies()
    choice = st.selectbox("Company", ["All companies"] + companies)

    rows = db.list_tasks(
        None if choice == "All companies" else choice
    )

    # Remove empty/invalid records
    rows = [
        r for r in rows
        if r.get("task_id") is not None
        and str(r["task_id"]).strip().lower() not in ("", "none", "null")
    ]

    st.caption(f"{len(rows)} record(s)")

    if rows:
        df = pd.DataFrame(rows)

        # Hide the status column
        df = df.drop(columns=["status"], errors="ignore")

        # Show only the latest 50 records
        st.dataframe(
            df.head(50),
            hide_index=True,
            use_container_width=True
        )

        st.divider()

        # Select any valid task to view its audit trail
        labels = {
            r["task_id"]:
                f'{r["task_id"]}  ·  {r["company"]}  ·  {r["category"]}'
            for r in rows
        }

        chosen = st.selectbox(
            "Open a task to see its details and audit trail",
            list(labels),
            format_func=labels.get
        )

        show_task(chosen)

    else:
        st.info("No tasks found.")
