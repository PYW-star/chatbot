--
-- PostgreSQL database dump
--

\restrict 8WgjM6xfYiPxEEKkR9WYlmauKBLog4kn02hpCf3hwU1MsV2vwdspi3RvmBKzy3J

-- Dumped from database version 13.23 (Debian 13.23-0+deb11u4)
-- Dumped by pg_dump version 13.23 (Debian 13.23-0+deb11u4)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.task DROP CONSTRAINT IF EXISTS fk_task_company;
ALTER TABLE IF EXISTS ONLY public.task DROP CONSTRAINT IF EXISTS fk_task_category;
ALTER TABLE IF EXISTS ONLY public.audit_log DROP CONSTRAINT IF EXISTS audit_log_task_id_fkey;
DROP INDEX IF EXISTS public.tasks_entity_idx;
DROP INDEX IF EXISTS public.tasks_date_idx;
DROP INDEX IF EXISTS public.tasks_category_idx;
DROP INDEX IF EXISTS public.company_name_unique;
DROP INDEX IF EXISTS public.audit_task_idx;
ALTER TABLE IF EXISTS ONLY public.task DROP CONSTRAINT IF EXISTS task_pkey;
ALTER TABLE IF EXISTS ONLY public.task_counter DROP CONSTRAINT IF EXISTS task_counter_pkey;
ALTER TABLE IF EXISTS ONLY public.company DROP CONSTRAINT IF EXISTS company_pkey;
ALTER TABLE IF EXISTS ONLY public.category DROP CONSTRAINT IF EXISTS category_pkey;
ALTER TABLE IF EXISTS ONLY public.category DROP CONSTRAINT IF EXISTS category_category_name_key;
ALTER TABLE IF EXISTS ONLY public.audit_log DROP CONSTRAINT IF EXISTS audit_log_pkey;
DROP TABLE IF EXISTS public.task_counter;
DROP TABLE IF EXISTS public.task;
DROP TABLE IF EXISTS public.company;
DROP TABLE IF EXISTS public.category;
DROP TABLE IF EXISTS public.audit_log;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: cosec_admin
--

CREATE TABLE public.audit_log (
    task_id character varying(10) NOT NULL,
    audit_id character varying(10) GENERATED ALWAYS AS (('A'::text || substr((task_id)::text, 2))) STORED,
    entry_no integer NOT NULL,
    action_type character varying(50) NOT NULL,
    old_value jsonb,
    new_value jsonb NOT NULL,
    audited_by character varying(100) NOT NULL,
    audited_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT audit_log_entry_no_check CHECK ((entry_no > 0))
);


ALTER TABLE public.audit_log OWNER TO cosec_admin;

--
-- Name: category; Type: TABLE; Schema: public; Owner: cosec_admin
--

CREATE TABLE public.category (
    category_id integer NOT NULL,
    category_name character varying(100) NOT NULL,
    category_desc character varying(200)
);


ALTER TABLE public.category OWNER TO cosec_admin;

--
-- Name: category_category_id_seq; Type: SEQUENCE; Schema: public; Owner: cosec_admin
--

ALTER TABLE public.category ALTER COLUMN category_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.category_category_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: company; Type: TABLE; Schema: public; Owner: cosec_admin
--

CREATE TABLE public.company (
    company_id integer NOT NULL,
    company_name character varying(100) NOT NULL,
    added_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.company OWNER TO cosec_admin;

--
-- Name: company_company_id_seq; Type: SEQUENCE; Schema: public; Owner: cosec_admin
--

ALTER TABLE public.company ALTER COLUMN company_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.company_company_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: task; Type: TABLE; Schema: public; Owner: cosec_admin
--

CREATE TABLE public.task (
    task_id character varying(10) NOT NULL,
    company_id integer NOT NULL,
    category_id integer NOT NULL,
    date_received date NOT NULL,
    raw_message text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(50) NOT NULL,
    CONSTRAINT task_task_id_check CHECK (((task_id)::text ~ '^T[0-9]{9}$'::text))
);


ALTER TABLE public.task OWNER TO cosec_admin;

--
-- Name: task_counter; Type: TABLE; Schema: public; Owner: cosec_admin
--

CREATE TABLE public.task_counter (
    counter_date date NOT NULL,
    last_no integer NOT NULL
);


ALTER TABLE public.task_counter OWNER TO cosec_admin;

--
-- Data for Name: audit_log; Type: TABLE DATA; Schema: public; Owner: cosec_admin
--

COPY public.audit_log (task_id, entry_no, action_type, old_value, new_value, audited_by, audited_at) FROM stdin;
T261113001	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "Annual Return", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:44:39.245524+00
T261113002	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "Change of Directors", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:45:10.384195+00
T261113003	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "Change of Registered Address", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:45:10.384195+00
T261113004	1	CREATE	\N	{"company": "XYZ Berhad", "category": "Annual Return", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:45:10.384195+00
T261113005	1	CREATE	\N	{"company": "Alpha Sdn Bhd", "category": "Annual Return", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:47:06.264958+00
T261113006	1	CREATE	\N	{"company": "Beta Sdn Bhd", "category": "Annual Return", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:47:06.264958+00
T261113007	1	CREATE	\N	{"company": "Gamma Bhd", "category": "Annual Return", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:47:06.264958+00
T261113008	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "KYC / Client Due Diligence", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:47:16.640367+00
T261113009	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "Share Transfer", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:47:16.640367+00
T261113010	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "Financial Statements", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:47:16.640367+00
T261112001	1	CREATE	\N	{"company": "Delta Sdn Bhd", "category": "Annual Return", "date_received": "2026-11-12"}	Paul Yeo	2026-11-13 08:49:12.844894+00
T261113011	1	CREATE	\N	{"company": "Echo Sdn Bhd", "category": "KYC / Client Due Diligence", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:49:12.844894+00
T261113012	1	CREATE	\N	{"company": "Golf Sdn Bhd", "category": "Change of Directors", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:49:50.149589+00
T261113013	1	CREATE	\N	{"company": "Golf Sdn Bhd", "category": "Change of Company Name", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:49:50.149589+00
T261113014	1	CREATE	\N	{"company": "Hotel Bhd", "category": "Beneficial Ownership / BO Reporting", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:49:50.149589+00
T261105001	1	CREATE	\N	{"company": "Lima Sdn Bhd", "category": "Annual Return", "date_received": "2026-11-05"}	Paul Yeo	2026-11-13 08:50:02.66803+00
T261113015	1	CREATE	\N	{"company": "Elaine sdn, bhd", "category": "KYC / Client Due Diligence", "date_received": "2026-11-13"}	Paul Yeo	2026-11-13 08:50:33.735888+00
T261113016	1	CREATE	\N	{"company": "Kilo Sdn Bhd", "category": "Shareholders' Resolutions", "date_received": "2026-11-13"}	Bean man	2026-11-13 09:16:03.776199+00
T261113017	1	CREATE	\N	{"company": "Kilo Sdn Bhd", "category": "Share Allotment", "date_received": "2026-11-13"}	Bean man	2026-11-13 09:16:03.776199+00
T261113018	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "Board Resolutions", "date_received": "2026-11-13"}	Bean man	2026-11-13 09:16:22.823258+00
T261116001	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "Annual Return", "date_received": "2026-11-16"}	Bean Man	2026-11-16 10:01:14.29434+00
T261116002	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "Change of Directors", "date_received": "2026-11-16"}	Bean Man	2026-11-16 10:01:43.77861+00
T261116003	1	CREATE	\N	{"company": "ABC Sdn Bhd", "category": "Change of Registered Address", "date_received": "2026-11-16"}	Bean Man	2026-11-16 10:01:43.77861+00
T261116004	1	CREATE	\N	{"company": "XYZ Berhad", "category": "Annual Return", "date_received": "2026-11-16"}	Bean Man	2026-11-16 10:01:43.77861+00
T261115001	1	CREATE	\N	{"company": "Lima Sdn Bhd", "category": "Change of Company Name", "date_received": "2026-11-15"}	Bean Man	2026-11-16 10:03:16.129805+00
T261115002	1	CREATE	\N	{"company": "Mike Berhad", "category": "Beneficial Ownership / BO Reporting", "date_received": "2026-11-15"}	Bean Man	2026-11-16 10:03:16.129805+00
T261116005	1	CREATE	\N	{"company": "Maju Jaya Sdn Bhd", "category": "Change of Registered Address", "date_received": "2026-11-16"}	Bean Man	2026-11-16 10:03:42.673889+00
T261110001	1	CREATE	\N	{"company": "Whiskey Sdn Bhd", "category": "Annual Return", "date_received": "2026-11-10"}	tim	2026-11-17 02:19:08.583479+00
T261110002	1	CREATE	\N	{"company": "Xray Bhd", "category": "Annual Return", "date_received": "2026-11-10"}	tim	2026-11-17 02:19:08.583479+00
T261110003	1	CREATE	\N	{"company": "Yankee Bhd", "category": "Annual Return", "date_received": "2026-11-10"}	tim	2026-11-17 02:19:08.583479+00
T261110004	1	CREATE	\N	{"company": "Xray Bhd", "category": "Financial Statements", "date_received": "2026-11-10"}	tim	2026-11-17 02:19:08.583479+00
\.


--
-- Data for Name: category; Type: TABLE DATA; Schema: public; Owner: cosec_admin
--

COPY public.category (category_id, category_name, category_desc) FROM stdin;
1	Company Incorporation	\N
2	Annual Return	\N
3	Financial Statements	\N
4	Change of Directors	\N
5	Change of Shareholders	\N
6	Share Transfer	\N
7	Share Allotment	\N
8	Change of Company Name	\N
9	Change of Registered Address	\N
10	Change of Business Address	\N
11	Company Constitution	\N
12	Board Resolutions	\N
13	Shareholders' Resolutions	\N
14	Beneficial Ownership / BO Reporting	\N
15	Company Charges	\N
16	Statutory Registers	\N
17	KYC / Client Due Diligence	\N
18	Compliance / Regulatory Matters	\N
19	Corporate Advisory	\N
20	General Enquiries	\N
21	Others	\N
\.


--
-- Data for Name: company; Type: TABLE DATA; Schema: public; Owner: cosec_admin
--

COPY public.company (company_id, company_name, added_at) FROM stdin;
1	ABC Sdn Bhd	2026-11-13 08:44:39.245524+00
4	XYZ Berhad	2026-11-13 08:45:10.384195+00
5	Alpha Sdn Bhd	2026-11-13 08:47:06.264958+00
6	Beta Sdn Bhd	2026-11-13 08:47:06.264958+00
7	Gamma Bhd	2026-11-13 08:47:06.264958+00
11	Delta Sdn Bhd	2026-11-13 08:49:12.844894+00
12	Echo Sdn Bhd	2026-11-13 08:49:12.844894+00
13	Golf Sdn Bhd	2026-11-13 08:49:50.149589+00
15	Hotel Bhd	2026-11-13 08:49:50.149589+00
16	Lima Sdn Bhd	2026-11-13 08:50:02.66803+00
17	Elaine sdn, bhd	2026-11-13 08:50:33.735888+00
18	Kilo Sdn Bhd	2026-11-13 09:16:03.776199+00
26	Mike Berhad	2026-11-16 10:03:16.129805+00
27	Maju Jaya Sdn Bhd	2026-11-16 10:03:42.673889+00
28	Whiskey Sdn Bhd	2026-11-17 02:19:08.583479+00
29	Xray Bhd	2026-11-17 02:19:08.583479+00
30	Yankee Bhd	2026-11-17 02:19:08.583479+00
\.


--
-- Data for Name: task; Type: TABLE DATA; Schema: public; Owner: cosec_admin
--

COPY public.task (task_id, company_id, category_id, date_received, raw_message, created_at, created_by) FROM stdin;
T261113001	1	2	2026-11-13	ABC Sdn Bhd annual return, received today	2026-11-13 08:44:39.245524+00	Paul Yeo
T261113002	1	4	2026-11-13	ABC Sdn Bhd - change director and update registered address. XYZ Berhad - annual return. Received today from Mr Tan.	2026-11-13 08:45:10.384195+00	Paul Yeo
T261113003	1	9	2026-11-13	ABC Sdn Bhd - change director and update registered address. XYZ Berhad - annual return. Received today from Mr Tan.	2026-11-13 08:45:10.384195+00	Paul Yeo
T261113004	4	2	2026-11-13	ABC Sdn Bhd - change director and update registered address. XYZ Berhad - annual return. Received today from Mr Tan.	2026-11-13 08:45:10.384195+00	Paul Yeo
T261113005	5	2	2026-11-13	Need annual return for Alpha Sdn Bhd, Beta Sdn Bhd and Gamma Bhd, received today	2026-11-13 08:47:06.264958+00	Paul Yeo
T261113006	6	2	2026-11-13	Need annual return for Alpha Sdn Bhd, Beta Sdn Bhd and Gamma Bhd, received today	2026-11-13 08:47:06.264958+00	Paul Yeo
T261113007	7	2	2026-11-13	Need annual return for Alpha Sdn Bhd, Beta Sdn Bhd and Gamma Bhd, received today	2026-11-13 08:47:06.264958+00	Paul Yeo
T261113008	1	17	2026-11-13	ABC Sdn Bhd received today:\n- KYC documents\n- share transfer\n- financial statements	2026-11-13 08:47:16.640367+00	Paul Yeo
T261113009	1	6	2026-11-13	ABC Sdn Bhd received today:\n- KYC documents\n- share transfer\n- financial statements	2026-11-13 08:47:16.640367+00	Paul Yeo
T261113010	1	3	2026-11-13	ABC Sdn Bhd received today:\n- KYC documents\n- share transfer\n- financial statements	2026-11-13 08:47:16.640367+00	Paul Yeo
T261112001	11	2	2026-11-12	Delta Sdn Bhd annual return, received yesterday. Echo Sdn Bhd KYC, received today.	2026-11-13 08:49:12.844894+00	Paul Yeo
T261113011	12	17	2026-11-13	Delta Sdn Bhd annual return, received yesterday. Echo Sdn Bhd KYC, received today.	2026-11-13 08:49:12.844894+00	Paul Yeo
T261113012	13	4	2026-11-13	Golf Sdn Bhd wants to change their company name and also the directors. Hotel Bhd wants help with BO reporting. Both came in today	2026-11-13 08:49:50.149589+00	Paul Yeo
T261113013	13	8	2026-11-13	Golf Sdn Bhd wants to change their company name and also the directors. Hotel Bhd wants help with BO reporting. Both came in today	2026-11-13 08:49:50.149589+00	Paul Yeo
T261113014	15	14	2026-11-13	Golf Sdn Bhd wants to change their company name and also the directors. Hotel Bhd wants help with BO reporting. Both came in today	2026-11-13 08:49:50.149589+00	Paul Yeo
T261105001	16	2	2026-11-05	Lima Sdn Bhd annual return received 5 Nov	2026-11-13 08:50:02.66803+00	Paul Yeo
T261113015	17	17	2026-11-13	Please do the KYC, received today	2026-11-13 08:50:33.735888+00	Paul Yeo
T261113016	18	13	2026-11-13	Kilo Sdn Bhd needs shareholders' resolution for share allotment, received today	2026-11-13 09:16:03.776199+00	Bean man
T261113017	18	7	2026-11-13	Kilo Sdn Bhd needs shareholders' resolution for share allotment, received today	2026-11-13 09:16:03.776199+00	Bean man
T261113018	1	12	2026-11-13	ABC Sdn. Bhd. needs a board resolution, received today	2026-11-13 09:16:22.823258+00	Bean man
T261116001	1	2	2026-11-16	ABC Sdn Bhd annual return, received today	2026-11-16 10:01:14.29434+00	Bean Man
T261116002	1	4	2026-11-16	ABC Sdn Bhd - change director and update registered address. XYZ Berhad - annual return. Received today from Mr Tan.	2026-11-16 10:01:43.77861+00	Bean Man
T261116003	1	9	2026-11-16	ABC Sdn Bhd - change director and update registered address. XYZ Berhad - annual return. Received today from Mr Tan.	2026-11-16 10:01:43.77861+00	Bean Man
T261116004	4	2	2026-11-16	ABC Sdn Bhd - change director and update registered address. XYZ Berhad - annual return. Received today from Mr Tan.	2026-11-16 10:01:43.77861+00	Bean Man
T261115001	16	8	2026-11-15	Lima Sdn Bhd wants to rename the company, and Mike Berhad needs help with its beneficial owner reporting. Both emailed us yesterday.	2026-11-16 10:03:16.129805+00	Bean Man
T261115002	26	14	2026-11-15	Lima Sdn Bhd wants to rename the company, and Mike Berhad needs help with its beneficial owner reporting. Both emailed us yesterday.	2026-11-16 10:03:16.129805+00	Bean Man
T261116005	27	9	2026-11-16	Tolong tukar alamat berdaftar untuk Maju Jaya Sdn Bhd, diterima hari ini	2026-11-16 10:03:42.673889+00	Bean Man
T261110001	28	2	2026-11-10	Annual return for Whiskey Sdn Bhd, Xray Bhd and Yankee Bhd, but Xray also needs the financial statements. Received 10 Nov.	2026-11-17 02:19:08.583479+00	tim
T261110002	29	2	2026-11-10	Annual return for Whiskey Sdn Bhd, Xray Bhd and Yankee Bhd, but Xray also needs the financial statements. Received 10 Nov.	2026-11-17 02:19:08.583479+00	tim
T261110003	30	2	2026-11-10	Annual return for Whiskey Sdn Bhd, Xray Bhd and Yankee Bhd, but Xray also needs the financial statements. Received 10 Nov.	2026-11-17 02:19:08.583479+00	tim
T261110004	29	3	2026-11-10	Annual return for Whiskey Sdn Bhd, Xray Bhd and Yankee Bhd, but Xray also needs the financial statements. Received 10 Nov.	2026-11-17 02:19:08.583479+00	tim
\.


--
-- Data for Name: task_counter; Type: TABLE DATA; Schema: public; Owner: cosec_admin
--

COPY public.task_counter (counter_date, last_no) FROM stdin;
2026-11-12	1
2026-11-05	1
2026-11-13	18
2026-11-15	2
2026-11-16	5
2026-11-10	4
\.


--
-- Name: category_category_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cosec_admin
--

SELECT pg_catalog.setval('public.category_category_id_seq', 21, true);


--
-- Name: company_company_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cosec_admin
--

SELECT pg_catalog.setval('public.company_company_id_seq', 31, true);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: cosec_admin
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (task_id, entry_no);


--
-- Name: category category_category_name_key; Type: CONSTRAINT; Schema: public; Owner: cosec_admin
--

ALTER TABLE ONLY public.category
    ADD CONSTRAINT category_category_name_key UNIQUE (category_name);


--
-- Name: category category_pkey; Type: CONSTRAINT; Schema: public; Owner: cosec_admin
--

ALTER TABLE ONLY public.category
    ADD CONSTRAINT category_pkey PRIMARY KEY (category_id);


--
-- Name: company company_pkey; Type: CONSTRAINT; Schema: public; Owner: cosec_admin
--

ALTER TABLE ONLY public.company
    ADD CONSTRAINT company_pkey PRIMARY KEY (company_id);


--
-- Name: task_counter task_counter_pkey; Type: CONSTRAINT; Schema: public; Owner: cosec_admin
--

ALTER TABLE ONLY public.task_counter
    ADD CONSTRAINT task_counter_pkey PRIMARY KEY (counter_date);


--
-- Name: task task_pkey; Type: CONSTRAINT; Schema: public; Owner: cosec_admin
--

ALTER TABLE ONLY public.task
    ADD CONSTRAINT task_pkey PRIMARY KEY (task_id);


--
-- Name: audit_task_idx; Type: INDEX; Schema: public; Owner: cosec_admin
--

CREATE INDEX audit_task_idx ON public.audit_log USING btree (task_id);


--
-- Name: company_name_unique; Type: INDEX; Schema: public; Owner: cosec_admin
--

CREATE UNIQUE INDEX company_name_unique ON public.company USING btree (lower((company_name)::text));


--
-- Name: tasks_category_idx; Type: INDEX; Schema: public; Owner: cosec_admin
--

CREATE INDEX tasks_category_idx ON public.task USING btree (category_id);


--
-- Name: tasks_date_idx; Type: INDEX; Schema: public; Owner: cosec_admin
--

CREATE INDEX tasks_date_idx ON public.task USING btree (date_received);


--
-- Name: tasks_entity_idx; Type: INDEX; Schema: public; Owner: cosec_admin
--

CREATE INDEX tasks_entity_idx ON public.task USING btree (company_id);


--
-- Name: audit_log audit_log_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: cosec_admin
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.task(task_id);


--
-- Name: task fk_task_category; Type: FK CONSTRAINT; Schema: public; Owner: cosec_admin
--

ALTER TABLE ONLY public.task
    ADD CONSTRAINT fk_task_category FOREIGN KEY (category_id) REFERENCES public.category(category_id);


--
-- Name: task fk_task_company; Type: FK CONSTRAINT; Schema: public; Owner: cosec_admin
--

ALTER TABLE ONLY public.task
    ADD CONSTRAINT fk_task_company FOREIGN KEY (company_id) REFERENCES public.company(company_id);


--
-- Name: TABLE audit_log; Type: ACL; Schema: public; Owner: cosec_admin
--

GRANT SELECT,INSERT ON TABLE public.audit_log TO cosec_staff;


--
-- Name: TABLE category; Type: ACL; Schema: public; Owner: cosec_admin
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.category TO cosec_staff;


--
-- Name: SEQUENCE category_category_id_seq; Type: ACL; Schema: public; Owner: cosec_admin
--

GRANT USAGE ON SEQUENCE public.category_category_id_seq TO cosec_staff;


--
-- Name: TABLE company; Type: ACL; Schema: public; Owner: cosec_admin
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.company TO cosec_staff;


--
-- Name: SEQUENCE company_company_id_seq; Type: ACL; Schema: public; Owner: cosec_admin
--

GRANT USAGE ON SEQUENCE public.company_company_id_seq TO cosec_staff;


--
-- Name: TABLE task; Type: ACL; Schema: public; Owner: cosec_admin
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.task TO cosec_staff;


--
-- Name: TABLE task_counter; Type: ACL; Schema: public; Owner: cosec_admin
--

GRANT SELECT,INSERT,UPDATE ON TABLE public.task_counter TO cosec_staff;


--
-- PostgreSQL database dump complete
--

\unrestrict 8WgjM6xfYiPxEEKkR9WYlmauKBLog4kn02hpCf3hwU1MsV2vwdspi3RvmBKzy3J

