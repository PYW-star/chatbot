from datetime import date

from dotenv import load_dotenv

load_dotenv()  # reads DB_* and ANTHROPIC_API_KEY from the .env file, if there is one

import pandas as pd
import streamlit as st

import db
import extract

st.set_page_config(page_title="CoSec Task Log", layout="wide")

# Stop early with a clear message if the database can't be reached.
try:
    db.check_connection()
except Exception as e:
    st.error(
        "Cannot connect to the database. Check the DB_* settings in your .env file "
        f"and that PostgreSQL is running.\n\nDetails: {e}"
    )
    st.stop()

FIELDS = ["company", "category", "date_received"]
COLUMNS = FIELDS + ["source_text"]   # source_text is only shown, never saved


def clean(value):
    """Turn blank/None/NaN cell values into None, otherwise a trimmed string."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip() or None


LABELS = {"company": "Company", "category": "Category", "date_received": "Date received"}
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
user = st.sidebar.text_input("Your name (saved as 'uploaded by')")

tab_chat, tab_records = st.tabs(["Chatbox", "Records"])

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
                message, db.get_categories(), db.get_companies(), date.today().isoformat()
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
                                  "Updates are not built yet, so I will treat it as a new task for now.")
                )
            for t in tasks:
                t["company"] = db.match_company(t.get("company"))
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
        df = df.astype(object).where(df.notna(), "")

        edited = st.data_editor(
            df,
            key=f"editor_{st.session_state.pending_id}",
            num_rows="dynamic",
            disabled=["source_text"],
            column_config={
                "source_text": st.column_config.TextColumn("from message"),
                "category": st.column_config.SelectboxColumn(
                    "category", options=db.get_categories()
                ),
            },
        )

        col1, col2 = st.columns(2)
        if col1.button("Save to database", type="primary"):
            if not user.strip():
                st.error("Enter your name in the sidebar first (saved as 'uploaded by').")
            else:
                rows = [{k: clean(v) for k, v in r.items()} for r in edited.to_dict("records")]
                bad = [i + 1 for i, r in enumerate(rows)
                       if not (r.get("company") and r.get("category") and r.get("date_received"))]
                if bad:
                    st.error(f"Row(s) {bad} are missing the company, category or date received.")
                else:
                    try:
                        saved_ids = db.insert_tasks(rows, st.session_state.pending_raw, user.strip())
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

# ---------- records ----------
with tab_records:
    companies = db.get_companies()
    choice = st.selectbox("Company", ["All companies"] + companies)
    rows = db.list_tasks(None if choice == "All companies" else choice)
    st.caption(f"{len(rows)} record(s)")
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True)

        st.divider()
        labels = {r["task_id"]: f'{r["task_id"]}  ·  {r["company"]}  ·  {r["category"]}' for r in rows}
        chosen = st.selectbox("Open a task to see its details and audit trail",
                              list(labels), format_func=labels.get)
        show_task(chosen)