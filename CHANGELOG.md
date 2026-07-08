# Changelog

## Day 27 - Smart Alerts AI Module + System Health
- Created utils/validate_data.py — 68 checks across tables, views, nulls, PK duplicates, date ranges (100/100 health)
- Created ai/smart_alerts/__init__.py and ai/smart_alerts/detector.py with SmartAlertDetector class
  - detect_traffic_anomalies(df) using IsolationForest (sklearn) with anomaly scoring
  - detect_conversion_drops(df) using 7-day rolling average statistical threshold
  - detect_bounce_spikes(df) using rolling average comparison
  - detect_engagement_drops(df) using session duration trend analysis
  - generate_alert_message(alert_type, data) using OpenAI or template fallback
  - run_all(df) runs all four detectors, returns combined Alert list
- Created ai/smart_alerts/alert_models.py with Alert dataclass (UUID, severity enum, to_dict) and AlertSummary dataclass (from_alerts, all_clear, to_dict)
- Created ai/smart_alerts/run_alerts.py — full pipeline: loads DB, runs detectors, saves to alerts table, saves markdown report
- Ran run_alerts.py: 7 WARNING alerts detected and saved to PostgreSQL
- Updated dashboard/pages/7_pipeline.py with SmartAlertDetector integration: real-time alert counts, expandable alert cards, alert trend chart
- Created ai/smart_alerts/scheduler.py with run_hourly_check, run_daily_check, schedule_alerts, get_next_run_time; includes Windows Task Scheduler setup guide
- Updated README AI Features table: Smart Alerts status changed from Planned to Complete
- Created utils/health_check.py: checks PostgreSQL, 6 tables, 6 views, 3 AI models, Smart Alerts module, report artifacts, 8 dashboard pages
- Ran health_check.py: 29/29 checks passed (100/100 score, ALL SYSTEMS HEALTHY)
- Added tests/test_smart_alerts.py with 13 tests covering initialization, anomaly detection, severity validation, DB save/delete, pipeline run, AlertSummary aggregation, bounce spike detection
- pytest: 301 passed (13 new smart alert tests)

## Day 26 - EDA Notebook + Data Dictionary
- Verified dim_dates fully populated (1,096 rows, 2023-01-01 to 2025-12-31)
- Created analysis/explore.ipynb with 7 analysis sections
- Section 1: Data Overview — row counts, date ranges, column names for all 4 raw tables
- Section 2: Traffic Analysis — daily sessions, channel breakdown, new vs returning chart
- Section 3: User Behavior — top pages, scroll depth distribution, event type pie
- Section 4: Conversion Analysis — daily CVR trend, goal completions by channel
- Section 5: SEO Analysis — word count distribution, load time histogram, word count vs load time scatter
- Section 6: Anomaly Detection — sessions chart with anomaly markers, severity distribution
- Section 7: Key Findings — 12 actionable insights across traffic, behavior, conversion, SEO
- Generated 12 EDA plot PNGs to data/processed/eda_plots/
- Created analysis/generate_summary.py — loads all metrics and saves platform_summary.txt
- Added 4 composite performance indexes (ga4_date_channel, srvlogs_time_url, click_event_page, scrape_url_wordcount)
  reducing query times by up to 99%
- Created data/DATA_DICTIONARY.md with full column descriptions, view descriptions, AI feature docs, and sample queries
- Added 21 unit tests in tests/test_eda.py
- All 297 tests passing with pytest

## Day 25 - User Behavior SQL + Smart Alerts System
- Created sql/queries/user_behavior.sql (8 queries: time on page, scroll depth, session duration, engagement scores, sticky pages)
- Created sql/queries/retention_analysis.sql (7 queries: DAU, WAU, MAU, stickiness, retention, churn, re-engagement)
- Created sql/queries/session_quality.sql (6 queries: high/low quality sessions, quality by channel, trend, best time/day)
- Created sql/queries/device_analysis.sql (6 queries: sessions over time, CVR, bounce, duration, load time, revenue by device)
- Enhanced utils/alerts.py with 7 smart alert checks: traffic_drop, bounce_spike, conversion_drop, page_speed_degradation, anomaly_detected, data_staleness, error_rate
- Added generate_alert_summary() aggregating all check results
- Created utils/alert_rules.py with AlertRule dataclass and 6 pre-defined rules; evaluate_all_rules() returns violations only
- Added alerts table to sql/schema.sql and applied to PostgreSQL (id, alert_type, severity, message, recommended_action, is_resolved, created_at, resolved_at)
- Updated dashboard/pages/7_pipeline.py: active alert summary KPIs, alert history table, resolution rate, Mark as Resolved button, alert trend log viewer
- Created utils/weekly_digest.py: generates weekly markdown digest saved to data/processed/digests/
- Ran weekly digest successfully
- Added retention analysis section to dashboard/pages/2_behavior.py (DAU/WAU/MAU KPIs, stickiness, retention chart, re-engagement by channel)
- Added session quality section to dashboard/pages/2_behavior.py (high/low quality pie, quality by channel bar, best-time heatmap)
- Added 7 new unit tests in tests/test_alerts.py
- All 276 tests passing

## Day 24 - SEO SQL + Predictive Analytics
- Created 3 new SQL queries: seo_content, keyword_analysis, page_speed
- Built TrafficForecaster using Facebook Prophet
- Built ConversionForecaster using Facebook Prophet
- Trained both forecasting models successfully
- Created dashboard/pages/8_forecasting.py
- Added forecast KPI cards: predicted sessions, CVR, confidence
- Added forecasting metrics to dashboard sidebar
- Predictive Analytics AI feature complete
- All tests passing

## Day 23 - Funnel SQL + Pipeline Monitor + Alerts
- Created 5 new SQL queries
- Updated run_all.py with dry-run and pipeline flags
- Created utils/pipeline_monitor.py
- Created dashboard/pages/7_pipeline.py
- Created utils/alerts.py monitoring system
- Added alerts to dashboard sidebar
- Added project metrics to home page
- All tests passing

## Day 22 - Conversion SQL Queries + SEO Dashboard Page
- Created 4 conversion SQL queries
- Created dashboard/pages/4_seo.py SEO page
- Added organic landing pages table
- Added word count vs engagement scatter plot
- Added content health table with scoring
- Added page load time distribution chart
- Added links analysis section
- All tests passing

## Day 21 - AI Report Generation + End-to-End Test
- Full pipeline test successful end to end
- All SQL views verified returning correct data
- Full test suite passing
- Created ai/report_generation/generator.py
- Created ai/report_generation/prompts.py
- Created ai/report_generation/formatter.py
- Created run_report.py pipeline script
- Created dashboard/pages/6_reports.py
- All tests passing

## Day 20 - Natural Language Query (NLQ)
- Created ai/nlq/nlq_engine.py with OpenAI integration
- Created ai/nlq/prompts.py with database schema prompts
- Created ai/nlq/safety.py SQL safety validation
- Created ai/nlq/cache.py query caching
- Added NLQ interface to dashboard sidebar
- Created Ask Your Data dashboard page
- All tests passing

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
