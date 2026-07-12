"""
populate_fct_sessions.py
Loads raw_ga4_sessions, joins with dim_dates and dim_pages,
and inserts into fct_sessions.
Truncates first for idempotent reruns; ON CONFLICT not applicable
to BIGSERIAL PKs, so TRUNCATE + INSERT is the correct pattern.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402
from utils.db import get_engine, query_df  # noqa: E402


def run(verbose: bool = True) -> int:
    engine = get_engine()

    with engine.begin() as conn:
        # Truncate for idempotency (BIGSERIAL has no natural dedup key)
        conn.execute(text("TRUNCATE fct_sessions RESTART IDENTITY"))

    # Build INSERT from raw tables via SQL — more efficient than row-by-row Python
    insert_sql = """
        INSERT INTO fct_sessions (
            session_id, user_pseudo_id,
            date_id, page_id,
            channel_grouping, source, medium, campaign,
            country, device_category, is_new_user,
            pageviews, session_duration_s, bounced,
            conversions, revenue
        )
        SELECT
            r.session_id,
            r.user_pseudo_id,
            d.date_id,
            p.page_id,
            r.channel_grouping,
            r.source,
            r.medium,
            r.campaign,
            r.country,
            r.device_category,
            (r.new_users > 0)          AS is_new_user,
            r.pageviews,
            r.session_duration_s,
            r.bounce                   AS bounced,
            r.conversions,
            r.revenue
        FROM raw_ga4_sessions r
        LEFT JOIN dim_dates  d ON d.full_date = r.session_date
        LEFT JOIN dim_pages  p ON p.url       = r.landing_page
        ON CONFLICT DO NOTHING
    """

    with engine.begin() as conn:
        result = conn.execute(text(insert_sql))
        inserted = result.rowcount

    if verbose:
        print(f"Inserted {inserted} rows into fct_sessions.")
    return inserted


if __name__ == "__main__":
    run(verbose=True)

    df_count = query_df("SELECT COUNT(*) AS n FROM fct_sessions")
    print(f"fct_sessions now has {df_count['n'].iloc[0]} rows.")

    df_sample = query_df("""
        SELECT fs.session_key, fs.date_id, fs.page_id,
               fs.channel_grouping, fs.device_category,
               fs.pageviews, fs.bounced
        FROM fct_sessions fs
        LIMIT 5
    """)
    print("\nSample rows:")
    print(df_sample.to_string(index=False))

    df_range = query_df("""
        SELECT dd.full_date
        FROM fct_sessions fs
        JOIN dim_dates dd ON dd.date_id = fs.date_id
        ORDER BY dd.full_date
        LIMIT 1
    """)
    df_range2 = query_df("""
        SELECT dd.full_date
        FROM fct_sessions fs
        JOIN dim_dates dd ON dd.date_id = fs.date_id
        ORDER BY dd.full_date DESC
        LIMIT 1
    """)
    print(
        f"\nDate range: {df_range['full_date'].iloc[0]} to {df_range2['full_date'].iloc[0]}"
    )

    # Verify FK integrity
    df_fk = query_df("""
        SELECT
            COUNT(*) FILTER (WHERE date_id IS NULL) AS null_date_fk,
            COUNT(*) FILTER (WHERE page_id IS NULL) AS null_page_fk
        FROM fct_sessions
    """)
    print(
        f"\nFK check: null date_id={df_fk['null_date_fk'].iloc[0]}, "
        f"null page_id={df_fk['null_page_fk'].iloc[0]}"
    )
