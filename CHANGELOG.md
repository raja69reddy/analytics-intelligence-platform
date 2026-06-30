# Changelog

## Day 14 - Week 2 Review
- Ran all 4 ingestion pipelines end to end (2,000 + 5,000 + 5,000 + 50 rows)
- Created ingestion/run_all.py orchestration script with formatted summary table
- All 108 tests passing across 7 test files
- Added utils/data_quality.py for null, duplicate, and date range checks
- Added performance indexes on all raw tables (session_date, log_time, event_time, event_name, url)
- Added utils/project_summary.py for project overview (tables, views, tests, ingestion times)
- Added timing logs (START/END) to all 4 ingestion scripts

## Day 13 - Page Behavior SQL Views
- Created 7 page behavior SQL views: vw_top_pages, vw_page_performance, vw_error_pages, vw_traffic_by_hour, vw_user_agents, vw_scroll_depth, vw_engagement_events
- Added page_analysis.sql with 5 queries
- Added weekly_report.sql with weekly summary, WoW growth, top pages, channels, and error rate
- Updated query_runner.py with run_view, get_view_columns, save_results_to_csv helpers
- All views tested and verified returning correct data
- All 108 unit tests passing

## Day 12 - SQL Views for Sessions by Channel
- Updated vw_traffic.sql with sessions by channel view (JOIN with dim_dates fallback)
- Created vw_daily_traffic.sql with 7-day rolling average
- Created vw_channel_performance.sql with channel share percentages
- Created vw_new_vs_returning.sql with new vs returning breakdown by date
- Created vw_device_breakdown.sql with device share and bounce rate
- Created vw_geo_performance.sql with top 10 countries by sessions
- Created sql/queries/traffic_summary.sql with 4 analysis queries
- Created utils/query_runner.py with run_query and run_query_string helpers
- Created tests/test_views.py with 24 view tests
- All 88 tests passing

## Day 11 - Clickstream + Scrape Pipelines
- Built ingestion/clickstream.py with full and incremental modes
- Built ingestion/scraper.py with upsert support
- Added verify scripts for both pipelines
- All 4 ingestion pipelines now complete
- All unit tests passing

## Day 10 - Log Parser + Enhanced Mock Data
- Updated gen_server_logs.py with 5,000 rows and more fields
- Created utils/log_parser.py with 5 parsing functions
- Updated server_logs.py to use log_parser
- Added server_log_analysis.sql queries
- Updated GA4 mock data with device and country columns
- All tests passing

## Day 9 - Server Logs Pipeline + GA4 Improvements
- Improved ga4.py incremental mode with --since flag
- Built ingestion/server_logs.py pipeline
- Added verify_server_logs.py
- All unit tests passing
- Updated vw_traffic.sql view

## Day 8 - GA4 Ingestion Pipeline
- Built ingestion/ga4.py with full and incremental modes
- Added error handling and logging
- Added verify_ga4.py verification script
- All data loaded into raw_ga4_sessions table
- Unit tests passing

## Day 7 - Week 1 Review
- Verified all 15 packages with setup_check.py
- Confirmed dim_dates has 1,096 rows (2023-01-01 to 2025-12-31)
- Refreshed all 4 mock data CSVs (1,000 + 2,000 + 50 + 5,000 rows)
- Added Project Architecture ASCII diagram to README
- Added full type hints to utils/helpers.py
- Created tests/test_helpers.py with 9 unit tests
- All 9 tests passing (pytest)

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
