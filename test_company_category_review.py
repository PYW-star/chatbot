"""Offline smoke tests for the company/category confirmation workflow.
Run: python test_company_category_review.py
Uses a temporary copy of the template; never modifies the real workbook.
"""
import os
import shutil
import tempfile
import importlib
from pathlib import Path

def run():
    source = Path(__file__).resolve().parent / 'CoSec_Task_Management_Sheet.xlsx'
    with tempfile.TemporaryDirectory() as temp:
        target = Path(temp) / 'test_co_sec.xlsx'
        shutil.copy2(source, target)
        os.environ['COSEC_EXCEL_PATH'] = str(target)
        import db
        importlib.reload(db)
        assert db.check_connection()
        companies = db.get_companies()
        categories = db.get_categories()
        assert 'BINGO INTELLECTUAL PROPERTY SDN. BHD.' in companies
        assert 'Board Resolutions' in categories
        rows = [{'company':'BINGO INTELLECTUAL PROPERTY SDN. BHD.', 'category':'Annual Return', 'date_received':'2026-11-19', 'fee_amount':None}]
        a = db.insert_tasks(rows, 'Received today: file annual return', 'Tester')
        assert a and db.get_task(a[0])['company'] == rows[0]['company']
        print('PASS  Existing company/category saved without approval')
        new_company='TITAN FUTURE SYSTEMS SDN. BHD.'
        new_category='Employment Pass / Work Permit'
        new = [{'company':new_company, 'category':new_category, 'date_received':'2026-11-19','fee_amount':None}]
        before=len(db.list_tasks())
        for kw in [{}, {'approve_new_companies':True}, {'approve_new_categories':True}]:
            try:
                db.insert_tasks(new,'testing', 'Tester', **kw)
            except ValueError:pass
            else:raise AssertionError(f'unapproved addition passed: {kw}')
            assert len(db.list_tasks())==before
        print('PASS  New company/category blocked without both approvals')
        ids=db.insert_tasks(new,'testing', 'Tester', approve_new_companies=True, approve_new_categories=True)
        assert len(ids)==1
        assert new_company in db.get_companies()
        assert new_category in db.get_categories()
        assert db.get_audit(ids[0])[0]['action_type']=='CREATE'
        print('PASS  Both names added only after approval; audit and task saved')
        again=db.insert_tasks(new,'testing again','Tester')
        assert again
        assert db.get_companies().count(new_company)==1
        assert db.get_categories().count(new_category)==1
        print('PASS  Reusing approved names does not produce duplicates')

if __name__=='__main__': run()
