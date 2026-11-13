-- Permission and role setup

CREATE ROLE cosec_admin LOGIN PASSWORD 'anything_change_it_a';

CREATE ROLE cosec_staff LOGIN PASSWORD 'anything_change_it_s';

CREATE DATABASE cosec_tasks OWNER cosec_admin;

REVOKE ALL ON DATABASE cosec_tasks FROM PUBLIC;
GRANT CONNECT ON DATABASE cosec_tasks TO cosec_staff;

-- Database creation

CREATE TABLE COMPANY (
    company_id      INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_name    VARCHAR(100) NOT NULL,
    added_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX company_name_unique ON company (lower(company_name));

CREATE TABLE CATEGORY (
    category_id     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_name   VARCHAR(100) NOT NULL UNIQUE,
    category_desc   VARCHAR(200)
);

-- Running number per received date, used to build task IDs like T261112001.
-- (T + YYMMDD of date received + 3-digit number for that day)
CREATE TABLE TASK_COUNTER (
    counter_date    DATE PRIMARY KEY,
    last_no         INT NOT NULL
);

CREATE TABLE TASK (
    task_id         VARCHAR(10) PRIMARY KEY CHECK (task_id ~ '^T[0-9]{9}$'),
    company_id      INT NOT NULL,
    category_id     INT NOT NULL,
    date_received   DATE NOT NULL,
    raw_message     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      VARCHAR(50) NOT NULL,


    CONSTRAINT FK_task_company 
    FOREIGN KEY (company_id) 
    REFERENCES COMPANY(company_id),

    CONSTRAINT FK_task_category 
    FOREIGN KEY (category_id) 
    REFERENCES CATEGORY(category_id)
);

CREATE INDEX tasks_entity_idx   ON TASK (company_id);
CREATE INDEX tasks_category_idx ON TASK (category_id);
CREATE INDEX tasks_date_idx     ON TASK (date_received);

CREATE TABLE AUDIT_LOG (
    task_id         VARCHAR(10) NOT NULL REFERENCES TASK(task_id),
    audit_id        VARCHAR(10) GENERATED ALWAYS AS ('A' || substr(task_id, 2)) STORED,
    entry_no        INT NOT NULL CHECK (entry_no > 0),
    action_type     VARCHAR(50) NOT NULL,
    old_value       JSONB,
    new_value       JSONB NOT NULL,
    audited_by      VARCHAR(100) NOT NULL,
    audited_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (task_id, entry_no)
);
CREATE INDEX audit_task_idx ON AUDIT_LOG (task_id);

INSERT INTO CATEGORY (category_name) VALUES
    ('Company Incorporation'), ('Annual Return'), ('Financial Statements'),
    ('Change of Directors'), ('Change of Shareholders'), ('Share Transfer'),
    ('Share Allotment'), ('Change of Company Name'), ('Change of Registered Address'),
    ('Change of Business Address'), ('Company Constitution'), ('Board Resolutions'),
    ('Shareholders'' Resolutions'), ('Beneficial Ownership / BO Reporting'),
    ('Company Charges'), ('Statutory Registers'), ('KYC / Client Due Diligence'),
    ('Compliance / Regulatory Matters'), ('Corporate Advisory'),
    ('General Enquiries'), ('Others');

-- PERMISSIONS FOR THE APP USER
-- It can read, add and edit records. It can never DELETE anything.
GRANT SELECT, INSERT, UPDATE ON COMPANY, CATEGORY, TASK, TASK_COUNTER TO cosec_STAFF;
-- The audit log is add-only: the app can read and insert, never change or delete.
GRANT SELECT, INSERT ON AUDIT_LOG TO cosec_staff;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA PUBLIC TO cosec_staff;