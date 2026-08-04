"""Prepend Day 54 entry to CHANGELOG.md (top of file, after heading)."""
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

DAY54 = """## Day 54 - PostgreSQL Indexes + Query Optimization
- Added 7 composite indexes to all raw/dim/fact tables via scripts/add_composite_indexes.py using CREATE INDEX IF NOT EXISTS: raw_ga4_sessions (session_date, channel_grouping, source), raw_server_logs (log_time, status_code, url), raw_clickstream_events (event_name, page_url, event_time), raw_scrape_pages (url, word_count, scraped_at), dim_dates (full_date, year, month), fct_sessions (date_id, channel_grouping), fct_events (date_id, event_name)
- Ran EXPLAIN ANALYZE on all 8 SQL views via scripts/explain_views.py; measured wall-clock (3-run avg) and PostgreSQL execution time; results saved to data/processed/query_times.csv; top 3 slowest: vw_traffic 331.5ms, vw_top_pages 25.2ms, vw_behavior 13.9ms
- Optimized top 3 slowest views via scripts/optimize_slow_views.py: (1) created materialized view mv_traffic_fast for vw_traffic with 3 covering indexes — reduced from 284.5ms to 8.6ms (-97%); (2) rewrote vw_top_pages with 90-day WHERE pre-filter — reduced from 24.0ms to 15.3ms (-36%); (3) rewrote vw_behavior with 90-day WHERE in both CTEs — reduced from 14.0ms to 12.2ms (-13%)
- Created sql/views/mat_daily_summary.sql materialized view: pre-aggregates daily KPIs from all 4 raw tables (GA4 sessions, clickstream events, server logs, dim_dates) into 22 columns including conversion_rate_pct and revenue_per_session; applied to PostgreSQL via scripts/create_mat_daily_summary.py with 3 covering indexes; 90 rows (90 days coverage)
- Added Step 5 to ingestion/run_all.py: REFRESH MATERIALIZED VIEW for mv_traffic_fast and mat_daily_summary after each full pipeline run; prints elapsed time per view; logs via logger
- Enhanced utils/db.py connection pooling: added pool_timeout=30 and pool_recycle=3600 to create_engine(); added pool_status() function returning live pool metrics (size, checkedin, checkedout, overflow); added pool init logging; updated test_connection() to print pool status

"""

text = CHANGELOG.read_text(encoding="utf-8")
if text.startswith("# Changelog\n"):
    new_text = "# Changelog\n\n" + DAY54 + text[len("# Changelog\n"):].lstrip("\n")
else:
    new_text = DAY54 + text

CHANGELOG.write_text(new_text, encoding="utf-8")
print("CHANGELOG.md updated with Day 54 entry.")
