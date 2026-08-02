"""Day 52 — Add PostgreSQL performance indexes and measure impact.

Creates composite indexes on all raw tables, runs EXPLAIN ANALYZE on the
top 3 slowest views, and prints before/after execution times.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_engine, query_df
from sqlalchemy import text


INDEXES = [
    # raw_ga4_sessions — composite on date + channel (may already exist)
    ("idx_ga4_session_date_channel",
     "CREATE INDEX IF NOT EXISTS idx_ga4_session_date_channel "
     "ON raw_ga4_sessions (session_date, channel_grouping)"),
    # raw_ga4_sessions — landing page for ROI queries
    ("idx_ga4_landing_page",
     "CREATE INDEX IF NOT EXISTS idx_ga4_landing_page "
     "ON raw_ga4_sessions (landing_page) WHERE landing_page IS NOT NULL"),
    # raw_ga4_sessions — device_category for mobile/desktop splits
    ("idx_ga4_device",
     "CREATE INDEX IF NOT EXISTS idx_ga4_device "
     "ON raw_ga4_sessions (device_category) WHERE device_category IS NOT NULL"),
    # raw_server_logs — log_time + url for traffic queries
    ("idx_srvlogs_logtime_url",
     "CREATE INDEX IF NOT EXISTS idx_srvlogs_logtime_url "
     "ON raw_server_logs (log_time, url)"),
    # raw_server_logs — status_code for error rate queries
    ("idx_srvlogs_status_code",
     "CREATE INDEX IF NOT EXISTS idx_srvlogs_status_code "
     "ON raw_server_logs (status_code)"),
    # raw_clickstream_events — event_name (task says event_type, column is event_name)
    ("idx_click_event_name_time",
     "CREATE INDEX IF NOT EXISTS idx_click_event_name_time "
     "ON raw_clickstream_events (event_name, event_time)"),
    # raw_clickstream_events — session_id for join performance
    ("idx_click_session_id",
     "CREATE INDEX IF NOT EXISTS idx_click_session_id "
     "ON raw_clickstream_events (session_id)"),
    # raw_scrape_pages — url + word_count composite
    ("idx_scrape_url_wc",
     "CREATE INDEX IF NOT EXISTS idx_scrape_url_wc "
     "ON raw_scrape_pages (url, word_count) WHERE http_status = 200"),
    # raw_scrape_pages — scraped_at for freshness queries
    ("idx_scrape_scraped_at",
     "CREATE INDEX IF NOT EXISTS idx_scrape_scraped_at "
     "ON raw_scrape_pages (scraped_at DESC)"),
]

SLOW_VIEWS = ["vw_traffic", "vw_seo", "vw_conversions"]


def measure_view_times(label: str) -> dict[str, float]:
    times: dict[str, float] = {}
    for v in SLOW_VIEWS:
        t0 = time.perf_counter()
        query_df(f"SELECT * FROM {v}")
        times[v] = round((time.perf_counter() - t0) * 1000, 1)
    print(f"\n{label}:")
    for v, ms in sorted(times.items(), key=lambda x: -x[1]):
        print(f"  {v}: {ms:.1f} ms")
    return times


def run():
    engine = get_engine()

    print("Measuring view times BEFORE indexes...")
    before = measure_view_times("Before indexes")

    print("\nCreating performance indexes...")
    with engine.begin() as conn:
        for name, ddl in INDEXES:
            try:
                conn.execute(text(ddl))
                print(f"  OK  {name}")
            except Exception as exc:
                print(f"  SKIP  {name}: {exc}")

    print("\nRunning EXPLAIN ANALYZE on top 3 slowest views...")
    with engine.connect() as conn:
        for v in SLOW_VIEWS:
            try:
                result = conn.execute(text(f"EXPLAIN ANALYZE SELECT * FROM {v}"))
                plan_lines = [row[0] for row in result]
                exec_line = next((l for l in plan_lines if "Execution Time" in l), "")
                print(f"  {v}: {exec_line.strip()}")
            except Exception as exc:
                print(f"  {v}: EXPLAIN error — {exc}")

    print("\nMeasuring view times AFTER indexes...")
    after = measure_view_times("After indexes")

    print("\n" + "=" * 55)
    print("SUMMARY — Query time improvement")
    print("=" * 55)
    print(f"{'View':<25} {'Before':>10} {'After':>10} {'Delta':>10}")
    print("-" * 55)
    for v in SLOW_VIEWS:
        b = before[v]
        a = after[v]
        delta = round(b - a, 1)
        print(f"{v:<25} {b:>9.1f}ms {a:>9.1f}ms {delta:>+9.1f}ms")

    print("\nAll performance indexes applied successfully.")


if __name__ == "__main__":
    run()
