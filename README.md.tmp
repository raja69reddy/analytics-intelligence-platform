# Analytics Intelligence Platform

A production-grade web analytics platform built with Python 3.14, PostgreSQL 17, and Streamlit â€” featuring a complete data pipeline (ingest â†’ transform â†’ validate â†’ alert), 17 SQL views, a multi-page dashboard, and 5 AI features.

**Phase 1 complete â€” 340 tests passing, 0 linting violations.**

---

## AI Features

| Feature | Description | Status |
|---------|-------------|--------|
| Anomaly Detection | IsolationForest detects traffic spikes/drops; saves to CSV + DB | Complete |
| Natural Language Query | OpenAI GPT-3.5 translates plain-English questions to SQL | Complete |
| AI Report Generation | LLM generates executive summaries for traffic, behavior, and conversions | Complete |
| Predictive Analytics | Facebook Prophet forecasts sessions and CVR 30 days ahead | Complete |
| Smart Alerts | Multi-signal KPI alert system with severity scoring; saves to PostgreSQL | Complete |

---

## Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Language | Python | 3.14 |
| Database | PostgreSQL | 17.10 |
| ORM / DB driver | SQLAlchemy + psycopg2 | 2.x |
| Dashboard | Streamlit | 1.x |
| Visualizations | Plotly | 5.x |
| Data manipulation | Pandas | 2.x |
| ML â€” Anomaly Detection | scikit-learn IsolationForest | 1.x |
| ML â€” Forecasting | Facebook Prophet | 1.x |
| AI â€” NLQ + Reports | OpenAI API (gpt-3.5-turbo) | â€” |
| Testing | pytest | 9.x |
| Formatting / Linting | black + flake8 | â€” |

---

## Performance Metrics (Phase 1)

| Metric | Value |
|--------|-------|
| Raw data rows | 17,200 (GA4: 2K, server: 5K, clickstream: 10K, scrape: 198) |
| Fact table rows | fct_sessions: 2,000 / fct_events: 10,000 |
| Dimension rows | dim_dates: 1,461 / dim_pages: 11 |
| SQL views | 17 views, all returning data |
| Dashboard pages | 8 pages |
| Test suite | 340 tests, 0 failures |
| Health check | 29/29 checks passing (100/100) |
| ETL pipeline time | ~2.6s (4 transform steps) |
| Anomaly detection | 1 low-severity anomaly in 90-day window |
| Smart alerts | 6 active warnings |

---

## Project Structure

```
web-analytics/
â”œâ”€â”€ ai/
â”‚   â”œâ”€â”€ anomaly_detection/     # IsolationForest detector + training pipeline
â”‚   â”œâ”€â”€ forecasting/           # Prophet-based traffic + CVR forecasters
â”‚   â”œâ”€â”€ nlq/                   # Natural language to SQL engine
â”‚   â”œâ”€â”€ report_generation/     # LLM executive report generator
â”‚   â”œâ”€â”€ smart_alerts/          # Multi-signal alert detector + scheduler
â”‚   â””â”€â”€ models/                # Saved .pkl model files
â”œâ”€â”€ analysis/
â”‚   â”œâ”€â”€ explore.ipynb          # 89-cell EDA notebook (16 sections)
â”‚   â””â”€â”€ generate_summary.py   # Platform summary script
â”œâ”€â”€ dashboard/
â”‚   â”œâ”€â”€ app.py                 # Streamlit home page + sidebar
â”‚   â”œâ”€â”€ components/            # Shared filters, charts, metrics
â”‚   â””â”€â”€ pages/
â”‚       â”œâ”€â”€ 1_traffic.py       # Traffic & Sessions
â”‚       â”œâ”€â”€ 2_behavior.py      # User Behavior & Funnels
â”‚       â”œâ”€â”€ 3_conversions.py   # Conversion Tracking
â”‚       â”œâ”€â”€ 4_seo.py           # SEO & Content
â”‚       â”œâ”€â”€ 5_nlq.py           # Ask Your Data (NLQ)
â”‚       â”œâ”€â”€ 6_reports.py       # AI Report Generation
â”‚       â”œâ”€â”€ 7_pipeline.py      # Pipeline Monitor + Alerts
â”‚       â””â”€â”€ 8_forecasting.py   # Predictive Analytics
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ raw/                   # CSV inputs (gitignored)
â”‚   â””â”€â”€ processed/             # Reports, alerts, anomalies, plots
â”œâ”€â”€ ingestion/
â”‚   â”œâ”€â”€ ga4.py                 # GA4 sessions â†’ raw_ga4_sessions
â”‚   â”œâ”€â”€ server_logs.py         # Server logs â†’ raw_server_logs
â”‚   â”œâ”€â”€ clickstream.py         # Events â†’ raw_clickstream_events
â”‚   â”œâ”€â”€ scraper.py             # Pages â†’ raw_scrape_pages
â”‚   â””â”€â”€ run_all.py             # Orchestrator: ingest + transform + validate + alert
â”œâ”€â”€ mock_data/                 # Synthetic data generators (4 sources)
â”œâ”€â”€ sql/
â”‚   â”œâ”€â”€ schema.sql             # All table DDL
â”‚   â”œâ”€â”€ views/                 # 17 SQL view definitions
â”‚   â”œâ”€â”€ populate_dim_pages.py  # Upsert page metadata
â”‚   â”œâ”€â”€ populate_fct_sessions.py
â”‚   â”œâ”€â”€ populate_fct_events.py
â”‚   â””â”€â”€ run_all_transforms.py  # Master ETL pipeline
â”œâ”€â”€ tests/                     # 340 pytest tests across 20 test files
â””â”€â”€ utils/
    â”œâ”€â”€ db.py                  # SQLAlchemy engine + query helpers
    â”œâ”€â”€ health_check.py        # 29-check system health monitor
    â”œâ”€â”€ data_quality.py        # Data quality report
    â”œâ”€â”€ validate_data.py       # 68 validation checks
    â”œâ”€â”€ smart_alerts/ ...      # (see ai/smart_alerts)
    â””â”€â”€ eda_reporter.py        # Auto-generates markdown EDA report
```

---

## Setup

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 15+ running locally (default port 5432)

### 2. Create the database

```sql
CREATE DATABASE web_analytics;
```

### 3. Python environment

```bash
cd web-analytics
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Configure credentials

```bash
cp .env.example .env
# Edit .env with your DB_HOST / DB_USER / DB_PASSWORD
# Optionally add OPENAI_API_KEY for NLQ + AI reports
```

### 5. Apply the schema

```bash
python sql/apply_schema.py
```

### 6. Generate mock data

```bash
python mock_data/gen_ga4.py
python mock_data/gen_server_logs.py
python mock_data/gen_scrape.py
python mock_data/gen_clickstream.py
```

### 7. Run the full pipeline

```bash
python ingestion/run_all.py --mode full
```

This runs ingestion + ETL transforms + data validation + smart alerts in one pass.

### 8. Launch the dashboard

```bash
streamlit run dashboard/app.py
```

Open http://localhost:8501 in your browser.

---

## Dashboard Pages

| Page | Key Features |
|------|-------------|
| Traffic & Sessions | Sessions, bounce rate, channel breakdown, new vs returning, device, geo |
| User Behavior | Top pages, funnel, scroll depth, engagement events, retention, session quality |
| Conversions | CVR over time, goal completions, revenue, funnel drop-off |
| SEO & Content | Organic pages, word count vs engagement, content health scoring |
| Ask Your Data | Natural language â†’ SQL â†’ results (OpenAI powered) |
| AI Reports | Auto-generated executive summaries with LLM analysis |
| Pipeline Monitor | Run logs, alert history, data quality status |
| Predictive Analytics | 30-day session + CVR forecasts using Prophet |

---

## SQL Views (17 total)

`vw_traffic`, `vw_daily_traffic`, `vw_channel_performance`, `vw_new_vs_returning`,
`vw_device_breakdown`, `vw_geo_performance`, `vw_top_pages`, `vw_page_performance`,
`vw_error_pages`, `vw_traffic_by_hour`, `vw_user_agents`, `vw_scroll_depth`,
`vw_engagement_events`, `vw_conversions`, `vw_funnel`, `vw_behavior`, `vw_seo`

---

## Running Tests

```bash
python -m pytest tests/ -v
```

340 tests, 0 failures (Phase 1).

---

## ðŸ“‹ Progress Log

âœ… **Day 1 â€” Project Scaffold**
- Created complete folder structure
- Set up .env.example with all required variables
- .gitignore covering Python, venv, __pycache__
- README skeleton with all sections

âœ… **Day 2 â€” Database Connection**
- utils/db.py with SQLAlchemy connection helper
- Connected to PostgreSQL web_analytics database
- Added python-dotenv for credential management
- Tested connection successfully

âœ… **Day 3 â€” SQL Schema**
- All 8 table definitions written in sql/schema.sql
- Applied schema to PostgreSQL database
- Tables created: raw_ga4_sessions, raw_server_logs,
  raw_scrape_pages, raw_clickstream_events, dim_pages,
  dim_dates, fct_sessions, fct_events

âœ… **Day 4 â€” Helper Functions + dim_dates Table**
- Created utils/helpers.py with parse_url, get_date_id, clean_user_agent
- Built sql/populate_dates.py script
- Filled dim_dates table with dates from 2023 to 2025
- Verified all rows inserted successfully into PostgreSQL

âœ… **Day 5 â€” Environment Verified + SQL Views + Queries**
- Created setup_check.py for environment verification
- Added docstrings to all utils functions
- Created 4 SQL views: traffic, behavior, conversions, SEO
- Created 3 reusable SQL queries
- Added CHANGELOG.md
- Added detailed comments to schema.sql

âœ… **Day 6 â€” Mock Data Generators**
- Created mock_data/gen_ga4.py â€” 1,000 rows of GA4 session data
- Created mock_data/gen_server_logs.py â€” 2,000 rows of server logs
- Created mock_data/gen_scrape.py â€” 50 rows of scraped pages
- Created mock_data/gen_clickstream.py â€” 5,000 rows of clickstream events
- All CSVs saved to data/raw/ folder

âœ… **Day 7 â€” Week 1 Review**
- Verified all packages and PostgreSQL connection
- Refreshed all 4 mock data CSVs
- Added Project Architecture ASCII diagram to README
- Added type hints to utils/helpers.py
- Created tests/test_helpers.py with 9 unit tests
- All tests passing with pytest

âœ… **Day 8 â€” GA4 Ingestion Pipeline**
- Created ingestion/ga4.py with --mode full and --mode incremental
- Added error handling and Python logging
- Created verify_ga4.py to verify data quality
- Loaded 1,000 rows into raw_ga4_sessions table
- All unit tests passing with pytest

âœ… **Day 9 â€” Server Logs Pipeline + GA4 Improvements**
- Improved GA4 incremental mode with --since date flag
- Created ingestion/server_logs.py with full and incremental modes
- Added error handling and logging to server_logs.py
- Created verify_server_logs.py for data quality checks
- Loaded 2,000 rows into raw_server_logs table
- All unit tests passing with pytest

âœ… **Day 10 â€” Log Parser + Enhanced Mock Data**
- Updated gen_server_logs.py â€” now generates 5,000 rows
- Created utils/log_parser.py with 5 parsing functions
- Updated server_logs.py to use log_parser functions
- Added server_log_analysis.sql with 4 analysis queries
- Updated GA4 mock data with device and country columns
- All unit tests passing with pytest

âœ… **Day 11 â€” Clickstream + Scrape Ingestion Pipelines**
- Created ingestion/clickstream.py with full and incremental modes
- Created ingestion/scraper.py with upsert support
- Added verify_clickstream.py and verify_scraper.py
- Loaded 5,000 clickstream events into raw_clickstream_events
- Loaded 50 scraped pages into raw_scrape_pages
- All 4 ingestion pipelines complete and tested

âœ… **Day 12 â€” Traffic SQL Views**
- Created 6 SQL views: daily traffic, channel performance,
  new vs returning, device breakdown, geo performance
- Added traffic_summary.sql with 4 analysis queries
- Built utils/query_runner.py for easy SQL execution
- All views tested and returning correct data
- All unit tests passing with pytest

âœ… **Day 13 â€” Page Behavior SQL Views**
- Created 7 SQL views: top pages, page performance,
  error pages, traffic by hour, user agents,
  scroll depth, engagement events
- Added page_analysis.sql with 5 analysis queries
- Added weekly_report.sql for weekly summaries
- Updated query_runner.py with 3 new helper functions
- All views tested and returning correct data
- All unit tests passing with pytest

âœ… **Day 14 â€” Week 2 Review**
- Ran all 4 ingestion pipelines successfully end to end
- Created ingestion/run_all.py orchestration script
- Full test suite passing (all 7 test files)
- Added utils/data_quality.py for data quality reporting
- Added performance indexes on all raw tables
- Added utils/project_summary.py for project overview
- All systems verified and working correctly

âœ… **Day 15 â€” Enhanced Mock Data + Dashboard Started**
- Updated clickstream generator to 10,000 rows
- Updated scrape generator to 100 rows with new columns
- Created dashboard/app.py with sidebar and global filters
- Created filters.py, metrics.py, charts.py components
- Created traffic page skeleton with 4 KPI cards
- Streamlit app running successfully on localhost:8501

âœ… **Day 16 â€” Traffic & Sessions Page Complete**
- Connected traffic page to real PostgreSQL data
- Added 4 KPI cards: sessions, users, pageviews, bounce rate
- Added sessions over time line chart with 7-day rolling avg
- Added channel bar chart and donut pie chart
- Added new vs returning users stacked bar chart
- Added device breakdown and geographic performance sections
- Added caching, loading spinners, and error handling
- Traffic page fully functional on localhost:8501

âœ… **Day 17 â€” User Behavior & Funnels Page Complete**
- Created dashboard/pages/2_behavior.py
- Added 4 KPI cards: pageviews, time on page, scroll depth, events
- Added top pages table with search and slow page highlighting
- Added conversion funnel visualization with drop-off percentages
- Added scroll depth histogram with color coding
- Added engagement events breakdown bar chart
- Added session duration distribution histogram
- Added engagement score calculation for top pages
- Added traffic heatmap by day and hour
- All tests passing with pytest

âœ… **Day 18 â€” Conversion Tracking Page Complete**
- Created vw_conversions.sql and vw_funnel.sql views
- Created dashboard/pages/3_conversions.py
- Added 4 KPI cards: CVR, goal completions, revenue, avg revenue
- Added conversion rate over time line chart
- Added goal completions by source/medium chart
- Added revenue by channel horizontal bar chart
- Added drop off waterfall chart
- Added conversion funnel with stage percentages
- Added channel contribution table with CSV download
- All tests passing with pytest

âœ… **Day 19 â€” AI Anomaly Detection**
- Created ai/ folder structure with 4 submodules
- Built AnomalyDetector class using scikit-learn IsolationForest
- Trained and saved traffic anomaly detection model
- Created run_detection.py pipeline script
- Added anomaly visualization to traffic dashboard page
- Anomaly dates marked with red dots on sessions chart
- Added severity badges: ðŸ”´ High ðŸŸ¡ Medium ðŸŸ¢ Low
- Added anomaly alerts to dashboard sidebar
- All tests passing with pytest

âœ… **Day 20 â€” Natural Language Query (NLQ) AI Feature**
- Created ai/nlq/nlq_engine.py â€” OpenAI powered SQL generator
- Created ai/nlq/prompts.py â€” database schema system prompts
- Created ai/nlq/safety.py â€” SQL injection prevention
- Created ai/nlq/cache.py â€” query result caching
- Created run_nlq.py CLI interface
- Tested with 5 example business questions successfully
- Added NLQ interface to dashboard sidebar
- Created dashboard/pages/5_nlq.py Ask Your Data page
- All unit tests passing with pytest

âœ… **Day 21 â€” AI Report Generation + End-to-End Test**
- Full pipeline test successful end to end
- All 12 SQL views verified returning correct data
- Full test suite passing with pytest
- Created ai/report_generation/generator.py with ReportGenerator class
- Created ai/report_generation/prompts.py with 5 AI prompts
- Created ai/report_generation/formatter.py for markdown and HTML output
- Created run_report.py â€” generates full AI executive summary
- Created dashboard/pages/6_reports.py AI Reports page
- Added report generation to dashboard sidebar
- 3 out of 3 AI features now complete âœ…

âœ… **Day 22 â€” Conversion SQL Queries + SEO Dashboard Page**
- Created conversion_rate.sql with 6 conversion metrics
- Created goal_completions.sql with 5 analysis queries
- Created revenue_analysis.sql with 6 revenue metrics
- Created funnel_analysis.sql with 5 funnel queries
- Created dashboard/pages/4_seo.py SEO page
- Added 4 KPI cards: organic sessions, load time, missing meta, word count
- Added top organic landing pages table
- Added word count vs engagement scatter plot with trend line
- Added content health table with color coded scoring
- Added page load time distribution histogram
- Added internal vs external links analysis
- All tests passing with pytest

âœ… **Day 23 â€” Funnel SQL + Pipeline Monitor + Alerts**
- Created 5 new SQL queries: funnel dropoff, user segments,
  content performance, anomaly report, cohort analysis
- Updated run_all.py with --dry-run and --pipeline flags
- Created utils/pipeline_monitor.py for run logging
- Created dashboard/pages/7_pipeline.py Pipeline Monitor
- Created utils/alerts.py monitoring system
- Added alerts to dashboard sidebar with severity badges
- Added project metrics to dashboard home page
- All tests passing with pytest

âœ… **Day 24 â€” SEO SQL Queries + Predictive Analytics**
- Created seo_content.sql with 8 SEO metrics
- Created keyword_analysis.sql with 7 content metrics
- Created page_speed.sql with 6 performance metrics
- Built TrafficForecaster using Facebook Prophet
- Built ConversionForecaster using Facebook Prophet
- Trained both forecasting models successfully
- Created dashboard/pages/8_forecasting.py
- Added forecast KPI cards: predicted sessions, CVR, confidence
- Added forecasting metrics to dashboard sidebar
- Predictive Analytics AI feature complete âœ…
- All tests passing with pytest

âœ… **Day 25 â€” User Behavior SQL + Smart Alerts System**
- Created user_behavior.sql (8 queries: time on page, scroll depth, session duration, engagement scores, sticky pages)
- Created retention_analysis.sql (7 queries: DAU, WAU, MAU, stickiness, retention rate, churn, re-engagement)
- Created session_quality.sql (6 queries: high/low quality sessions, quality by channel, trend, best time of day/day of week)
- Created device_analysis.sql (6 queries: sessions over time, CVR, bounce, duration, load time, revenue by device)
- Enhanced utils/alerts.py with 7 smart alert checks including traffic_drop, bounce_spike, conversion_drop, page_speed_degradation, anomaly_detected, data_staleness, error_rate
- Created utils/alert_rules.py with AlertRule dataclass and 6 pre-defined rules
- Added alerts table to PostgreSQL schema
- Updated pipeline dashboard with alert management UI (resolution tracking, alert trend viewer)
- Created utils/weekly_digest.py â€” generates markdown performance digest
- Added retention analysis section to behavior dashboard (DAU/WAU/MAU KPIs, stickiness, retention chart)
- Added session quality section to behavior dashboard (pie, channel bar, best-time heatmap)
- 276 tests passing with pytest

âœ… **Day 26 â€” EDA Notebook + Data Dictionary**
- Verified dim_dates table fully populated with 1,096 rows
- Created analysis/explore.ipynb with 7 analysis sections
- Analyzed traffic, behavior, conversions, SEO and anomalies
- Key findings documented in markdown cells
- Created analysis/generate_summary.py platform summary script
- Added composite performance indexes for faster queries
- Created data/DATA_DICTIONARY.md with full column descriptions
- All unit tests passing with pytest

âœ… **Day 27 â€” Smart Alerts AI Module + System Health Check**
- Created utils/validate_data.py â€” 68 validation checks, 100/100 health score
- Built ai/smart_alerts/ module: SmartAlertDetector with 4 detectors
  - IsolationForest anomaly detection, rolling-average CVR/bounce/engagement checks
  - Alert and AlertSummary dataclasses with severity enum (CRITICAL/WARNING/OK)
  - run_alerts.py pipeline: loads DB, detects, saves to alerts table, generates markdown report
  - scheduler.py: hourly/daily scheduling with Windows Task Scheduler documentation
- Ran run_alerts.py: 7 WARNING alerts detected and saved to PostgreSQL
- Updated 7_pipeline.py dashboard with smart alert cards and trend chart
- Updated AI Features table: Smart Alerts marked Complete
- Created utils/health_check.py: 29/29 checks (PostgreSQL, tables, views, models, artifacts, pages)
- Ran health_check.py: 100/100 score, ALL SYSTEMS HEALTHY
- 301 tests passing with pytest (13 new smart alert tests)

âœ… **Day 28 â€” EDA Funnel + Fact Tables ETL**
- Created populate_fct_sessions.py â€” joins GA4 with dim tables; 2,000 rows loaded, 0 null FKs
- Created populate_fct_events.py â€” joins clickstream with dim tables; 10,000 rows loaded, 0 null FKs
- Created populate_dim_pages.py â€” upserts page metadata from 3 raw sources; 11 pages
- Extended dim_dates to 2026 to cover actual mock data date range
- Added funnel visualization to EDA notebook (Section 8: Homepage â†’ Purchase funnel)
- Added cohort retention analysis with heatmap (Section 9: weekly cohorts, channel breakdown)
- Added platform executive summary to EDA notebook (Section 10: all KPIs in one table)
- Created sql/run_all_transforms.py master ETL pipeline (4 steps, 3.22s total)
- Updated run_all.py â€” now runs full ingestion + transform + validate + alerts pipeline
- All unit tests passing with pytest (316 passed)

âœ… **Day 29 â€” EDA Notebook Complete**
- Added funnel visualization to analysis/explore.ipynb (Section 11: deep-dive with device breakdown)
- Added channel performance analysis section (Section 12: trend line, pie, bounce/CVR bars)
- Added device and geographic analysis sections (Sections 13 & 14: device share, geo top-10)
- Added time series heatmap analysis (Section 15: hour x DOW heatmap, peak traffic windows)
- Added AI insights summary with 5 actionable findings and 4 saved PNG plots (Section 16)
- Created utils/eda_reporter.py â€” auto-generates markdown report from live DB metrics
- Ran eda_reporter.py: 10 key metrics printed, eda_report_2026-07-10.md saved
- All unit tests passing with pytest (331 passed, 15 new EDA notebook tests)
