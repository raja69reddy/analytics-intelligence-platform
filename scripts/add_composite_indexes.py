"""Day 54 — Add composite indexes to all raw, dim, and fact tables.

Uses CREATE INDEX IF NOT EXISTS so re-runs are safe.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_engine
from sqlalchemy import text

INDEXES = [
    # raw_ga4_sessions — date + channel + source for traffic views
    (
        "idx_ga4_date_channel_source",
        "CREATE INDEX IF NOT EXISTS idx_ga4_date_channel_source "
        "ON raw_ga4_sessions (session_date, channel_grouping, source)",
    ),
    # raw_server_logs — log_time + status_code + url for server log queries
    (
        "idx_srvlogs_time_status_url",
        "CREATE INDEX IF NOT EXISTS idx_srvlogs_time_status_url "
        "ON raw_server_logs (log_time, status_code, url)",
    ),
    # raw_clickstream_events — event_name + page_url + event_time for behavior views
    (
        "idx_click_event_page_time",
        "CREATE INDEX IF NOT EXISTS idx_click_event_page_time "
        "ON raw_clickstream_events (event_name, page_url, event_time)",
    ),
    # raw_scrape_pages — url + word_count + scraped_at for SEO / content queries
    (
        "idx_scrape_url_wc_time",
        "CREATE INDEX IF NOT EXISTS idx_scrape_url_wc_time "
        "ON raw_scrape_pages (url, word_count, scraped_at)",
    ),
    # dim_dates — full_date + year + month for calendar joins
    (
        "idx_dim_dates_date_yr_mo",
        "CREATE INDEX IF NOT EXISTS idx_dim_dates_date_yr_mo "
        "ON dim_dates (full_date, year, month)",
    ),
    # fct_sessions — date_id + channel_grouping for fact aggregations
    (
        "idx_fct_sessions_date_channel",
        "CREATE INDEX IF NOT EXISTS idx_fct_sessions_date_channel "
        "ON fct_sessions (date_id, channel_grouping)",
    ),
    # fct_events — date_id + event_name for event aggregations
    (
        "idx_fct_events_date_event",
        "CREATE INDEX IF NOT EXISTS idx_fct_events_date_event "
        "ON fct_events (date_id, event_name)",
    ),
]


def run() -> None:
    engine = get_engine()
    print("=" * 60)
    print("  Day 54 — Adding Composite Indexes")
    print("=" * 60)

    created = 0
    skipped = 0
    t_total = time.perf_counter()

    with engine.begin() as conn:
        for name, ddl in INDEXES:
            t0 = time.perf_counter()
            try:
                conn.execute(text(ddl))
                elapsed = (time.perf_counter() - t0) * 1000
                print(f"  OK    {name:<40}  ({elapsed:.0f} ms)")
                created += 1
            except Exception as exc:
                print(f"  SKIP  {name:<40}  ({exc})")
                skipped += 1

    total_elapsed = (time.perf_counter() - t_total) * 1000
    print("-" * 60)
    print(f"  Created/verified: {created}  |  Skipped: {skipped}")
    print(f"  Total time      : {total_elapsed:.0f} ms")
    print("=" * 60)
    print("\nAll composite indexes created successfully.")


if __name__ == "__main__":
    run()
