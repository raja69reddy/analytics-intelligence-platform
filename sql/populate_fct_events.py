"""
populate_fct_events.py
Loads raw_clickstream_events, joins with dim_dates and dim_pages,
and inserts into fct_events.
TRUNCATE + INSERT pattern for idempotent reruns.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from utils.db import get_engine, query_df


def run(verbose: bool = True) -> int:
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE fct_events RESTART IDENTITY"))

    # Normalize clickstream page_url (strip trailing slash except for root '/')
    # then join dim_pages on the normalized path
    insert_sql = """
        INSERT INTO fct_events (
            event_time, date_id, session_id, user_pseudo_id,
            page_id, event_name, scroll_depth_pct, event_value, device_category
        )
        SELECT
            r.event_time,
            d.date_id,
            r.session_id,
            r.user_pseudo_id,
            p.page_id,
            r.event_name,
            r.scroll_depth_pct,
            r.event_value,
            r.device_category
        FROM raw_clickstream_events r
        LEFT JOIN dim_dates  d ON d.full_date = r.event_time::date
        LEFT JOIN dim_pages  p ON p.url =
            CASE
                WHEN r.page_url IS NULL OR r.page_url = '' THEN NULL
                WHEN r.page_url = '/' THEN '/'
                ELSE regexp_replace(r.page_url, '/$', '')
            END
        ON CONFLICT DO NOTHING
    """

    with engine.begin() as conn:
        result = conn.execute(text(insert_sql))
        inserted = result.rowcount

    if verbose:
        print(f"Inserted {inserted} rows into fct_events.")
    return inserted


if __name__ == "__main__":
    run(verbose=True)

    df_count = query_df("SELECT COUNT(*) AS n FROM fct_events")
    print(f"fct_events now has {df_count['n'].iloc[0]} rows.")

    df_sample = query_df("""
        SELECT event_key, date_id, page_id, event_name,
               device_category, scroll_depth_pct, event_value
        FROM fct_events
        LIMIT 5
    """)
    print("\nSample rows:")
    print(df_sample.to_string(index=False))

    df_dist = query_df("""
        SELECT event_name, COUNT(*) AS n
        FROM fct_events
        GROUP BY event_name
        ORDER BY n DESC
    """)
    print("\nEvent type distribution:")
    print(df_dist.to_string(index=False))

    df_fk = query_df("""
        SELECT
            COUNT(*) FILTER (WHERE date_id IS NULL) AS null_date_fk,
            COUNT(*) FILTER (WHERE page_id IS NULL) AS null_page_fk
        FROM fct_events
    """)
    print(f"\nFK check: null date_id={df_fk['null_date_fk'].iloc[0]}, "
          f"null page_id={df_fk['null_page_fk'].iloc[0]}")
