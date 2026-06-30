# Changelog

## Day 6 - Mock Data Generators
- gen_ga4.py: 1,000 rows of GA4 session data
- gen_server_logs.py: 2,000 rows of server logs
- gen_scrape.py: 50 rows of scraped pages
- gen_clickstream.py: 5,000 rows of clickstream events

## Day 5 - Environment Verified + SQL Views + Queries
- Verified all Python packages with setup_check.py
- Added docstrings to utils/helpers.py and utils/db.py
- Created 4 SQL views: vw_traffic, vw_behavior, vw_conversions, vw_seo
- Created 3 reusable SQL queries: top_pages, channel_breakdown, daily_sessions
- Added detailed comments to sql/schema.sql

## Day 4 - Helper Functions + dim_dates
- Created utils/helpers.py with parse_url, get_date_id, clean_user_agent
- Created sql/populate_dates.py
- Filled dim_dates with dates from 2023-01-01 to 2025-12-31

## Day 3 - SQL Schema
- Wrote all 8 table definitions in sql/schema.sql
- Applied schema to web_analytics PostgreSQL database
- Created 4 SQL views: vw_traffic, vw_behavior, vw_conversions, vw_seo

## Day 2 - Database Connection
- Created utils/db.py with SQLAlchemy connection helper
- Connected to PostgreSQL web_analytics database
- Tested connection successfully

## Day 1 - Project Scaffold
- Created complete folder structure
- Set up .env.example with all required environment variables
- Added .gitignore and README skeleton
