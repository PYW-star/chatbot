"""
Checks that the chatbot splits messages into the right tasks and companies.
 
Run:   python text_extract.py
Run manual Excel test checklist: python text_extract.py --manual
With DEMO_MODE=true, tests the limited keyword-based extractor (no AI key needed).
With DEMO_MODE=false, requires ANTHROPIC_API_KEY and calls the real AI (API costs apply).
This script never writes to your Excel workbook.
"""
from datetime import date, timedelta
 
from dotenv import load_dotenv
 
load_dotenv()
 
import extract  # noqa: E402
import argparse
 
# Match the default approved categories in db.py
CATEGORIES = [
    "Company Incorporation", "Annual Return", "Financial Statements",
    "Change of Directors", "Change of Shareholders", "Share Transfer",
    "Share Allotment", "Change of Company Name", "Change of Registered Address",
    "Change of Business Address", "Company Constitution", "Board Resolutions",
    "Shareholders' Resolutions", "Beneficial Ownership / BO Reporting",
    "Company Charges", "Statutory Registers", "KYC / Client Due Diligence",
    "Compliance / Regulatory Matters", "Corporate Advisory",
    "General Enquiries", "Others",
]
KNOWN_COMPANIES = ["ABC Sdn Bhd", "XYZ Sdn Bhd", "GreenTech Sdn Bhd", "Sunrise Trading Sdn Bhd", "Blue Ocean Sdn Bhd"]
 
TODAY = date.today()
T = TODAY.isoformat()
Y = (TODAY - timedelta(days=1)).isoformat()
 
# Each case: (name, message, expected set of (company, category, date_received), expected intent)
CASES = [
    ("Two companies, own tasks each",
     "ABC Sdn Bhd - change director and update registered address. "
     "XYZ Berhad - annual return. Received today from Mr Tan.",
     {("ABC Sdn Bhd", "Change of Directors", T),
      ("ABC Sdn Bhd", "Change of Registered Address", T),
      ("XYZ Berhad", "Annual Return", T)}, "new_task"),
 
    ("One instruction, several companies",
     "Need annual return for Alpha Sdn Bhd, Beta Sdn Bhd and Gamma Bhd, received today",
     {("Alpha Sdn Bhd", "Annual Return", T),
      ("Beta Sdn Bhd", "Annual Return", T),
      ("Gamma Bhd", "Annual Return", T)}, "new_task"),
 
    ("Bullet list, one company",
     "ABC Sdn Bhd received today:\n- KYC documents\n- share transfer\n- financial statements",
     {("ABC Sdn Bhd", "KYC / Client Due Diligence", T),
      ("ABC Sdn Bhd", "Share Transfer", T),
      ("ABC Sdn Bhd", "Financial Statements", T)}, "new_task"),
 
    ("Different dates per company",
     "Delta Sdn Bhd annual return, received yesterday. Echo Sdn Bhd KYC, received today.",
     {("Delta Sdn Bhd", "Annual Return", Y),
      ("Echo Sdn Bhd", "KYC / Client Due Diligence", T)}, "new_task"),
 
    ("Company missing",
     "Please do the KYC, received today",
     {(None, "KYC / Client Due Diligence", T)}, "new_task"),
 
    ("Date missing",
     "Foxtrot Sdn Bhd wants to change company name",
     {("Foxtrot Sdn Bhd", "Change of Company Name", None)}, "new_task"),
 
    ("Known company spelled slightly differently",
     "ABC Sdn. Bhd. needs a board resolution, received today",
     {("ABC Sdn Bhd", "Board Resolutions", T)}, "new_task"),
 
    ("Not a task",
     "hello, how are you?",
     set(), "unknown"),
]
 
 
# New cases use the same expected (company, category, received date) convention.
# "AI-only" cases are skipped in demo mode, because the demo extractor is just a
# keyword matcher; it is not expected to understand complex natural language.
EXTRA_CASES = [
    ("TC01 - Single director change",
     "ABC Sdn Bhd requested a change of director. Received today.",
     {("ABC Sdn Bhd", "Change of Directors", T)}, "new_task", False, None),
    ("TC02 - Two independent company tasks",
     "ABC Sdn Bhd requested a change of director. Received today.\n"
     "XYZ Sdn Bhd requested an annual return. Received today.",
     {("ABC Sdn Bhd", "Change of Directors", T),
      ("XYZ Sdn Bhd", "Annual Return", T)}, "new_task", False, None),
    ("TC03 - Two categories for one company",
     "ABC Sdn Bhd needs an annual return and a board resolution, received today.",
     {("ABC Sdn Bhd", "Annual Return", T),
      ("ABC Sdn Bhd", "Board Resolutions", T)}, "new_task", False, None),
    ("TC04 - No company specified",
     "Please do the KYC, received today",
     {(None, "KYC / Client Due Diligence", T)}, "new_task", False, None),
    ("TC05 - No received date specified",
     "ABC Sdn Bhd requested a board resolution.",
     {("ABC Sdn Bhd", "Board Resolutions", None)}, "new_task", False, None),
    ("TC06 - Unknown category",
     "ABC Sdn Bhd requested an unfamiliar specialist service, received today.",
     {("ABC Sdn Bhd", None, T)}, "new_task", False, None),
    ("TC07 - Optional fee left blank",
     "ABC Sdn Bhd requested a board resolution, received today.",
     {("ABC Sdn Bhd", "Board Resolutions", T)}, "new_task", False, None),
    ("TC08 - Explicit RM 250 fee",
     "ABC Sdn Bhd requested a board resolution with a fee of RM 250, received today.",
     {("ABC Sdn Bhd", "Board Resolutions", T)}, "new_task", False, 250.0),
    ("TC09 - Non-task greeting",
     "Hello, how are you?",
     set(), "unknown", False, None),
    ("TC10 - Identify update intention",
     "Update ABC Sdn Bhd's director change task. Documents received today.",
     {("ABC Sdn Bhd", "Change of Directors", T)}, "update", True, None),
    ("TC11 - Billing instruction fee extraction",
     "Charge ABC Sdn Bhd for Maybank board resolutions - RM 250, received today.",
     {("ABC Sdn Bhd", "Board Resolutions", T)}, "new_task", True, 250.0),
    ("TC12 - Several companies, single instruction",
     "Annual return for ABC Sdn Bhd and XYZ Sdn Bhd, received today.",
     {("ABC Sdn Bhd", "Annual Return", T),
      ("XYZ Sdn Bhd", "Annual Return", T)}, "new_task", True, None),
]

# TC13-TC21 are integration tests and must be carried out in the Streamlit UI;
# extraction-only checks cannot prove that an Excel workbook was saved correctly.
MANUAL_TESTS = [
    ("TC13", "Save one reviewed task", "One row is added to the Tasks worksheet."),
    ("TC14", "Save two reviewed tasks", "Both rows are saved, with unique task IDs."),
    ("TC15", "Company task history", "Task appears under the right company in the Records tab."),
    ("TC16", "Restart and check persistence", "Saved task is still present after restarting Streamlit."),
    ("TC17", "Audit log", "Audit_Log has a corresponding CREATE entry."),
    ("TC18", "Invalid category in a batch", "Invalid category rejects the batch without partial writes."),
    ("TC19", "Leave Fee (RM) empty on confirmation", "Excel fee_amount cell is blank, not zero."),
    ("TC20", "Enter Fee (RM) = 250", "Excel fee_amount cell contains numeric 250."),
    ("TC21", "Workbook inaccessible or invalid path", "App reports a useful error without corrupting data."),
]


def main():
    parser = argparse.ArgumentParser(description="Test extraction without changing Excel records")
    parser.add_argument("--manual", action="store_true", help="Print manual Streamlit/Excel test checklist")
    args = parser.parse_args()
    if args.manual:
        print("Manual app/Excel checklist (do NOT run these against real client data):\n")
        for code, instruction, expected in MANUAL_TESTS:
            print(f"{code}: {instruction}\n  Expected: {expected}\n")
        return

    demo = extract.demo_mode()
    print("DEMO MODE: only basic extraction can be tested; AI-only cases will be skipped.\n" if demo
          else "LIVE AI MODE: this will call your configured Anthropic API and may incur charges.\n")
    base_cases = [(name, msg, exp, intent, True, None) for name, msg, exp, intent in CASES]
    # Existing legacy cases test nuanced splitting and were originally designed
    # for the AI, so do not report failures as regressions of the demo keyword matcher.
    cases = base_cases + EXTRA_CASES
    passed = failed = skipped = 0
    for name, message, expected, expected_intent, ai_only, fee in cases:
        if demo and ai_only:
            print(f"SKIP   {name} (requires live AI)")
            skipped += 1
            continue
        try:
            result = extract.extract_tasks(message, CATEGORIES, KNOWN_COMPANIES, T)
            got = {(t["company"], t["category"], t["date_received"]) for t in result["tasks"]}
            ok = got == expected and result["intent"] == expected_intent
            if fee is not None:
                ok = ok and len(result["tasks"]) == 1 and result["tasks"][0].get("fee_amount") == fee
            elif name.startswith("TC07"):
                ok = ok and len(result["tasks"]) == 1 and result["tasks"][0].get("fee_amount") is None
        except Exception as e:
            failed += 1
            print(f"ERROR  {name}: {e}\n")
            continue
        if ok:
            passed += 1
        else:
            failed += 1
        print(("PASS   " if ok else "FAIL   ") + name)
        if not ok:
            print("   message :", message.replace("\n", " | "))
            print("   expected:", sorted(expected, key=str), "| intent", expected_intent, "| fee", fee)
            print("   got     :", sorted(got, key=str), "| intent", result["intent"],
                  "| fees", [t.get("fee_amount") for t in result["tasks"]])
    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")
    print("For Excel saving, audit, and restart tests: python text_extract.py --manual")


if __name__ == "__main__":
    main()
