# Changelog

All notable changes to this project are documented here.

---

## Day 5 — Requirements Verified
- Installed and verified all packages from requirements.txt
- Created utils/setup_check.py to confirm all imports succeed
- Updated requirements.txt to versions compatible with Python 3.14

## Day 4 — Helper Functions + dim_dates
- Added utils/helpers.py with parse_url, get_date_id, clean_user_agent
- Created sql/populate_dates.py to fill dim_dates from 2023-01-01 to 2025-12-31
- Verified 1,096 rows inserted successfully into PostgreSQL

## Day 3 — SQL Schema
- Wrote all 8 table definitions in sql/schema.sql
- Applied schema to web_analytics PostgreSQL database
- Tables: raw_ga4_sessions, raw_server_logs, raw_scrape_pages,
  raw_clickstream_events, dim_pages, dim_dates, fct_sessions, fct_events
- Created 4 SQL views: vw_traffic, vw_behavior, vw_conversions, vw_seo

## Day 2 — Database Connection
- Created utils/db.py with SQLAlchemy engine and connection helpers
- Connected to PostgreSQL web_analytics database using python-dotenv
- Tested connection successfully

## Day 1 — Project Scaffold
- Created complete folder structure (dashboard, ingestion, mock_data, sql, utils)
- Set up .env.example with all required environment variables
- Added .gitignore covering Python, venv, __pycache__, data files
- Created README skeleton with all sections
