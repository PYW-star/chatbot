-- Permission and role setup

CREATE ROLE cosec_admin LOGIN PASSWORD 'anything_change_it_a';

CREATE ROLE cosec_staff LOGIN PASSWORD 'anything_change_it_s';

CREATE DATABASE cosec_tasks OWNER cosec_admin;

REVOKE ALL ON DATABASE cosec_tasks FROM PUBLIC;
GRANT CONNECT ON DATABSE cosec_tasks TO cosec_staff;

-- Database creation
