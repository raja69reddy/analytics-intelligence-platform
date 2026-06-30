# Changelog

## Day 19 - AI Anomaly Detection
- Created ai/ folder structure with anomaly_detection, nlq, report_generation, forecasting submodules
- Built AnomalyDetector class using scikit-learn IsolationForest
- Trained and saved traffic anomaly detection model (ai/models/traffic_anomaly_model.pkl)
- Created run_detection.py pipeline script — detects anomalies and saves to data/processed/anomalies.csv
- Added anomaly visualization to traffic dashboard page (red dots on sessions chart)
- Added severity badges: High / Medium / Low to anomaly summary table
- Added anomaly alerts section to dashboard sidebar (st.error/st.warning by severity)
- All 170 tests passing with pytest

## Day 18 - Conversion Tracking Dashboard Page
- Created sql/views/vw_conversions.sql with synthetic CVR by channel (Email 6.5% → Social 1.8%) and $52 avg revenue
- Created sql/views/vw_funnel.sql with 5 monotone-decreasing stages from raw_ga4_sessions
- Created dashboard/pages/3_conversions.py with 9 sections
- Added 4 KPI cards: overall CVR%, total goal completions, total revenue, avg revenue/session
- Added CVR over time bar chart with green/red coloring vs 3.5% target + 7-day rolling average + dashed target line
- Added goal completions by source/medium grouped bar chart (top 15)
- Added revenue by channel horizontal bar chart with dollar labels outside
- Added funnel drop-off waterfall chart (green=continuing, red=drop-off) using go.Waterfall
- Added conversion funnel visualization with go.Funnel, biggest drop-off stage highlighted in red
- Added channel contribution table (sessions, conversions, CVR%, revenue) with CSV download
- Added conversion trend by day of week bar chart with best day highlighted in green
- Added @st.cache_data(ttl=300) on both query loaders + sidebar cache clear button
- Added st.spinner and try/except with st.stop for DB error handling
- Added tests/test_conversions_page.py with 17 tests (9 for vw_conversions, 8 for vw_funnel)
- All 141 tests passing across 8 test files

## Day 17 - User Behavior Page Complete
- Created dashboard/pages/2_behavior.py with 10 sections
- Added 4 KPI cards: total page views, avg time on page, avg scroll depth, total events
- Added top pages table with inline URL search and red highlight for slow pages (>1000ms)
- Added conversion funnel visualization: Homepage → Product → Cart → Checkout → Purchase
- Added scroll depth histogram with color-coded buckets (red=low → green=high)
- Added engagement events breakdown bar chart with percentage labels
- Added session duration distribution histogram (0-30s to 10m+)
- Added engagement score bar chart (top 10 pages, Viridis color gradient)
- Added page views over time line chart with optional URL filter
- Added traffic heatmap by day of week × hour using Plotly Heatmap
- Added @st.cache_data(ttl=300) on all 8 query loaders
- Added st.spinner and try/except with friendly error message
- Added tests/test_behavior_page.py with 16 tests
- All 124 tests passing across 10 test files

## Day 16 - Traffic & Sessions Dashboard Page
- Updated dashboard/pages/1_traffic.py with real PostgreSQL data from all 6 traffic views
- Added debug data shapes expander showing row counts for each view
- Added 5 KPI cards (sessions, users, pageviews, bounce rate, duration) with % change vs previous period
- Added sessions over time line chart with dashed 7-day rolling average overlay
- Added traffic by channel: horizontal bar chart (sorted descending) + donut pie side by side
- Added new vs returning users stacked bar chart over time
- Added device breakdown: sessions pie + bounce rate bar chart in two columns
- Added geographic performance: top countries table + horizontal bar chart
- Added raw data table with sortable columns, CSV download button, and last updated timestamp
- Added @st.cache_data(ttl=300) wrappers on all 6 view loaders
- Added cache clear button and TTL notice in sidebar
- Added st.spinner while loading data from PostgreSQL
- Added try/except with friendly error message and st.stop on DB failure

## Day 15 - Mock Data Enhanced + Dashboard Started
- Updated gen_clickstream.py with 10,000 rows and new columns (session_duration, device_type, browser, referrer_url)
- Updated gen_scrape.py with 100 rows and new columns (page_type, load_time_ms, internal_links, external_links)
- Created dashboard/app.py main entry point with sidebar, global filters, project stats
- Created dashboard/components/filters.py with get_date_filter, get_channel_filter, get_page_filter, get_device_filter, apply_filters
- Created dashboard/components/metrics.py with KPI card helpers and format functions
- Created dashboard/components/charts.py with line, bar, pie, funnel, scatter chart wrappers
- Created dashboard/pages/1_traffic.py with 5 KPI cards and session charts
- Streamlit app verified running on localhost:8501

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
