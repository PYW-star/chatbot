"""
Checks that the chatbot splits messages into the right tasks and companies.

Run:   python test_extract.py
Needs: ANTHROPIC_API_KEY in your .env (or set in the terminal). It does NOT touch the database.
Each test calls the real AI, so it costs a tiny amount per run.
"""
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()

import extract  # noqa: E402

# Keep this list the same as the categories in setup_2_tables.sql
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
KNOWN_COMPANIES = ["ABC Sdn Bhd"]

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


def main():
    passed = 0
    for name, message, expected, expected_intent in CASES:
        try:
            result = extract.extract_tasks(message, CATEGORIES, KNOWN_COMPANIES, T)
            got = {(t["company"], t["category"], t["date_received"]) for t in result["tasks"]}
            ok = got == expected and result["intent"] == expected_intent
        except Exception as e:  # noqa: BLE001
            print(f"ERROR  {name}: {e}\n")
            continue
        passed += ok
        print(("PASS   " if ok else "FAIL   ") + name)
        if not ok:
            print("   message :", message.replace("\n", " | "))
            print("   expected:", sorted(expected, key=str), "| intent", expected_intent)
            print("   got     :", sorted(got, key=str), "| intent", result["intent"])
        print()
    print(f"{passed}/{len(CASES)} passed")


if __name__ == "__main__":
    main()