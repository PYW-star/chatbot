# CoSec Task Log — local Excel edition

This conversion is based on the original `chatbot-cleanup-app(1).zip` app and keeps its `app.py` interface and extraction workflow. It uses a **local `.xlsx` workbook**, not PostgreSQL.

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this folder and run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` (demo mode works without an AI key).
4. Run `streamlit run app.py`.
5. Enter your name, type an instruction, review the extraction, then click **Save to Excel**.
6. Open **Records** to see saved tasks and their audit history.

The app uses `CoSec_Task_Management.xlsx` in this folder by default. You can set an absolute `COSEC_EXCEL_PATH` in `.env` to change its location. The app creates a new workbook if one is missing. Its sheets are `Companies`, `Categories`, `Tasks`, `Task_Counter`, and `Audit_Log`.

**No SQL commands or `DB_*` settings are needed.** `cosec_database.sql.NOT_USED` is retained only as a reference to the old schema.

## Important limitations

- This preserves the **original** app's functionality. It now supports an optional fee amount (RM) on each task. It does not yet implement owner-approved new categories/companies or updates to existing tasks. The existing app treats update requests as new tasks.
- Saving a task automatically creates unknown companies, as in the original code. Categories must be chosen from the current list.
- The workbook is intended for **one Streamlit process / one computer**, not shared multi-user access. A file lock protects against simultaneous writes by this app; Excel editing while Streamlit saves can still cause conflicts. Keep the workbook closed in Excel when using the app.
- Saving is atomic at the file level, but back up the `.xlsx` separately. There is no automatic migration of records already saved in PostgreSQL.
- Demo mode uses keyword rules, not AI. For real AI, use an approved Anthropic API key and `DEMO_MODE=false`. Some instructions require manual correction during review.
- The app does not authenticate users. Use only synthetic/anonymised test content until your organisation approves a deployment model.

## Optional fees

During **Review before saving**, enter an amount in **Fee (RM) — optional**, or leave it empty to store a truly blank Excel cell. `0` is different from blank. AI/demo extraction attempts to detect explicit RM amounts, but check the amount before saving. The Excel `Tasks` sheet has a new `fee_amount` column. Existing workbooks using the previous schema are upgraded automatically on startup without deleting records; back them up first. Fees are not automatically marked as paid/collected.

## Date Received correction (Nov 2026)

- The app passes the current date in Malaysia's `Asia/Kuala_Lumpur` timezone to the extractor.
- Demo mode only extracts dates explicitly associated with receiving the instruction (e.g. `received today`, `received 18/11/2026`). A deadline, filing date, effective date, or meeting date is **not** a received date.
- If no received date is stated, the review table leaves it blank. Enter the real received date in `YYYY-MM-DD` format before saving.
- Numeric dates in demo mode follow Malaysian `DD/MM/YYYY` convention.
- Date regression tests: `python test_dates.py`. These tests do not modify Excel records.
- Live AI's contextual date interpretation has **not** been verified; review dates before saving.
