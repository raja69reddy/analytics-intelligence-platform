# Analytics Intelligence Platform

A production-grade analytics platform built with Python, PostgreSQL, and Streamlit — enhanced with AI-powered insights, natural language querying, and automated report generation.

## 🤖 AI Features (In Progress)
| Feature | Description | Status |
|---------|-------------|--------|
| Anomaly Detection | Auto-detect traffic spikes and drops using ML | ✅ Complete |
| Natural Language Query | Ask questions in plain English, get SQL results | 🔄 In Progress |
| AI Report Generation | Auto-generate insights summaries using LLM | 🔄 In Progress |
| Predictive Analytics | Forecast traffic and conversions 30 days ahead | 📅 Planned |
| Smart Alerts | AI-powered alerts for KPI threshold breaches | 📅 Planned |

## 📋 Progress Log

✅ **Day 1 — Project Scaffold**
- Created complete folder structure
- Set up .env.example with all required variables
- .gitignore covering Python, venv, __pycache__
- README skeleton with all sections

✅ **Day 2 — Database Connection**
- utils/db.py with SQLAlchemy connection helper
- Connected to PostgreSQL web_analytics database
- Added python-dotenv for credential management
- Tested connection successfully

✅ **Day 3 — SQL Schema**
- All 8 table definitions written in sql/schema.sql
- Applied schema to PostgreSQL database
- Tables created: raw_ga4_sessions, raw_server_logs,
  raw_scrape_pages, raw_clickstream_events, dim_pages,
  dim_dates, fct_sessions, fct_events

✅ **Day 4 — Helper Functions + dim_dates Table**
- Created utils/helpers.py with parse_url, get_date_id, clean_user_agent
- Built sql/populate_dates.py script
- Filled dim_dates table with dates from 2023 to 2025
- Verified all rows inserted successfully into PostgreSQL

✅ **Day 5 — Environment Verified + SQL Views + Queries**
- Created setup_check.py for environment verification
- Added docstrings to all utils functions
- Created 4 SQL views: traffic, behavior, conversions, SEO
- Created 3 reusable SQL queries
- Added CHANGELOG.md
- Added detailed comments to schema.sql

✅ **Day 6 — Mock Data Generators**
- Created mock_data/gen_ga4.py — 1,000 rows of GA4 session data
- Created mock_data/gen_server_logs.py — 2,000 rows of server logs
- Created mock_data/gen_scrape.py — 50 rows of scraped pages
- Created mock_data/gen_clickstream.py — 5,000 rows of clickstream events
- All CSVs saved to data/raw/ folder

✅ **Day 7 — Week 1 Review**
- Verified all packages and PostgreSQL connection
- Refreshed all 4 mock data CSVs
- Added Project Architecture ASCII diagram to README
- Added type hints to utils/helpers.py
- Created tests/test_helpers.py with 9 unit tests
- All tests passing with pytest

✅ **Day 8 — GA4 Ingestion Pipeline**
- Created ingestion/ga4.py with --mode full and --mode incremental
- Added error handling and Python logging
- Created verify_ga4.py to verify data quality
- Loaded 1,000 rows into raw_ga4_sessions table
- All unit tests passing with pytest

✅ **Day 9 — Server Logs Pipeline + GA4 Improvements**
- Improved GA4 incremental mode with --since date flag
- Created ingestion/server_logs.py with full and incremental modes
- Added error handling and logging to server_logs.py
- Created verify_server_logs.py for data quality checks
- Loaded 2,000 rows into raw_server_logs table
- All unit tests passing with pytest

✅ **Day 10 — Log Parser + Enhanced Mock Data**
- Updated gen_server_logs.py — now generates 5,000 rows
- Created utils/log_parser.py with 5 parsing functions
- Updated server_logs.py to use log_parser functions
- Added server_log_analysis.sql with 4 analysis queries
- Updated GA4 mock data with device and country columns
- All unit tests passing with pytest

✅ **Day 11 — Clickstream + Scrape Ingestion Pipelines**
- Created ingestion/clickstream.py with full and incremental modes
- Created ingestion/scraper.py with upsert support
- Added verify_clickstream.py and verify_scraper.py
- Loaded 5,000 clickstream events into raw_clickstream_events
- Loaded 50 scraped pages into raw_scrape_pages
- All 4 ingestion pipelines complete and tested

✅ **Day 12 — Traffic SQL Views**
- Created 6 SQL views: daily traffic, channel performance,
  new vs returning, device breakdown, geo performance
- Added traffic_summary.sql with 4 analysis queries
- Built utils/query_runner.py for easy SQL execution
- All views tested and returning correct data
- All unit tests passing with pytest

✅ **Day 13 — Page Behavior SQL Views**
- Created 7 SQL views: top pages, page performance,
  error pages, traffic by hour, user agents,
  scroll depth, engagement events
- Added page_analysis.sql with 5 analysis queries
- Added weekly_report.sql for weekly summaries
- Updated query_runner.py with 3 new helper functions
- All views tested and returning correct data
- All unit tests passing with pytest

✅ **Day 14 — Week 2 Review**
- Ran all 4 ingestion pipelines successfully end to end
- Created ingestion/run_all.py orchestration script
- Full test suite passing (all 7 test files)
- Added utils/data_quality.py for data quality reporting
- Added performance indexes on all raw tables
- Added utils/project_summary.py for project overview
- All systems verified and working correctly

✅ **Day 15 — Enhanced Mock Data + Dashboard Started**
- Updated clickstream generator to 10,000 rows
- Updated scrape generator to 100 rows with new columns
- Created dashboard/app.py with sidebar and global filters
- Created filters.py, metrics.py, charts.py components
- Created traffic page skeleton with 4 KPI cards
- Streamlit app running successfully on localhost:8501

✅ **Day 16 — Traffic & Sessions Page Complete**
- Connected traffic page to real PostgreSQL data
- Added 4 KPI cards: sessions, users, pageviews, bounce rate
- Added sessions over time line chart with 7-day rolling avg
- Added channel bar chart and donut pie chart
- Added new vs returning users stacked bar chart
- Added device breakdown and geographic performance sections
- Added caching, loading spinners, and error handling
- Traffic page fully functional on localhost:8501

✅ **Day 17 — User Behavior & Funnels Page Complete**
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

✅ **Day 18 — Conversion Tracking Page Complete**
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

## Project Architecture

```
Data Sources          Raw Layer              Dimension / Fact         Dashboard
─────────────         ────────────────       ──────────────────       ─────────────────────
GA4 Export    ──►  raw_ga4_sessions    ──►  fct_sessions        ──►  Traffic & Sessions
Server Logs   ──►  raw_server_logs     ──►  dim_pages           ──►  User Behavior
Web Scraper   ──►  raw_scrape_pages    ──►  dim_dates           ──►  Conversions
Clickstream   ──►  raw_clickstream     ──►  fct_events          ──►  SEO & Content
                        │
                        ▼
                   SQL Views
                   ─────────────
                   vw_traffic
                   vw_behavior
                   vw_conversions
                   vw_seo
```

## Stack

| Layer | Tool |
|-------|------|
| Database | PostgreSQL 15+ |
| Language | Python 3.11+ |
| Data manipulation | Pandas, SQLAlchemy, psycopg2 |
| Dashboard | Streamlit |
| Visualizations | Plotly |
| AI/ML | scikit-learn, Prophet, OpenAI API |

## Project Structure

```
web-analytics/
├── dashboard/
│   ├── app.py                  # Streamlit entry point
│   ├── components/filters.py   # Shared sidebar filters
│   └── pages/
│       ├── 1_traffic.py
│       ├── 2_behavior.py
│       ├── 3_conversions.py
│       └── 4_seo.py
├── ingestion/
│   ├── ga4.py                  # raw_ga4_sessions → fct_sessions
│   ├── clickstream.py          # raw_clickstream_events → fct_events
│   ├── server_logs.py          # raw_server_logs → dim_pages
│   └── scraper.py              # raw_scrape_pages → dim_pages
├── mock_data/
│   ├── gen_ga4.py
│   ├── gen_server_logs.py
│   ├── gen_scrape.py
│   └── gen_clickstream.py
├── sql/
│   ├── schema.sql              # All table DDL
│   ├── apply_schema.py         # Run once to initialise DB
│   └── views/
│       ├── vw_traffic.sql
│       ├── vw_behavior.sql
│       ├── vw_conversions.sql
│       └── vw_seo.sql
├── utils/
│   ├── db.py                   # SQLAlchemy engine + helpers
│   └── helpers.py              # Date IDs, URL parsing, dim_dates loader
├── .env.example
└── requirements.txt
```

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
```

### 5. Apply the schema

```bash
python sql/apply_schema.py
```

---

## Load mock data (works without real data)

Run all four generators — this populates every raw table with 90 days of
realistic synthetic data:

```bash
python mock_data/gen_ga4.py          --mode full --days 90
python mock_data/gen_server_logs.py  --mode full --days 90
python mock_data/gen_scrape.py       --mode full
python mock_data/gen_clickstream.py  --mode full --days 90
```

---

## Run ingestion pipelines

Transform raw tables into the fact/dimension layer:

```bash
# Full reload
python ingestion/ga4.py         --mode full
python ingestion/clickstream.py --mode full
python ingestion/server_logs.py --mode full
python ingestion/scraper.py     --mode full

# Incremental (pick up new rows since a date)
python ingestion/ga4.py         --mode incremental --since 2024-06-01
python ingestion/clickstream.py --mode incremental --since 2024-06-01
```

---

## Launch the dashboard

```bash
streamlit run dashboard/app.py
```

Open http://localhost:8501 in your browser.

---

## Dashboard pages

| Page | KPIs |
|------|------|
| **Traffic & Sessions** | Sessions, pageviews, bounce rate, channel breakdown, new vs returning, device split |
| **User Behavior** | Top pages, avg time on page, scroll depth, event types, session funnel |
| **Conversions** | CVR over time, revenue, goal completions, channel contribution |
| **SEO & Content** | Organic landing pages, word count vs engagement scatter, load time distribution, content health |

All pages share a sidebar with **date range**, **channel**, and **page URL** filters.

---

## Incremental pipeline schedule (optional)

You can run the ingestion scripts nightly via Windows Task Scheduler or cron:

```bash
# Example: run at 02:00 every day
python ingestion/ga4.py --mode incremental --since $(date -d "yesterday" +%Y-%m-%d)
```
