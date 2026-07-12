"""
Verification script for raw_clickstream_events data quality.

Usage:
    python ingestion/verify_clickstream.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df

TABLE = "raw_clickstream_events"


def run_verification() -> None:
    print(f"\n{'='*52}")
    print("  raw_clickstream_events Verification Report")
    print(f"{'='*52}")

    # Total row count
    total = int(query_df(f"SELECT COUNT(*) AS n FROM {TABLE}")["n"].iloc[0])
    print(f"\nTotal rows: {total:,}")

    # Event type distribution
    df_evt = query_df(f"""
        SELECT event_name, COUNT(*) AS cnt,
               ROUND(100.0 * COUNT(*) / {total}, 1) AS pct
        FROM {TABLE}
        GROUP BY event_name ORDER BY cnt DESC
    """)
    print("\nEvent type distribution:")
    for _, r in df_evt.iterrows():
        print(f"  {r['event_name']:<15} {int(r['cnt']):>6,}  ({r['pct']}%)")

    # Top 5 pages by event count
    df_pages = query_df(f"""
        SELECT page_url, COUNT(*) AS cnt
        FROM {TABLE}
        GROUP BY page_url ORDER BY cnt DESC
        LIMIT 5
    """)
    print("\nTop 5 pages by event count:")
    for _, r in df_pages.iterrows():
        print(f"  {str(r['page_url']):<35} {int(r['cnt']):>5,}")

    # Scroll depth statistics
    df_scroll = query_df(f"""
        SELECT
            MIN(scroll_depth_pct)                AS min_pct,
            MAX(scroll_depth_pct)                AS max_pct,
            ROUND(AVG(scroll_depth_pct), 1)      AS avg_pct
        FROM {TABLE}
        WHERE scroll_depth_pct IS NOT NULL
    """)
    r = df_scroll.iloc[0]
    print("\nScroll depth (0-100 pct):")
    print(f"  min={r['min_pct']}  max={r['max_pct']}  avg={r['avg_pct']}")

    # Null value check
    key_cols = ["event_time", "session_id", "event_name", "page_url"]
    print("\nNull value check:")
    found_nulls = False
    for col in key_cols:
        n_null = int(
            query_df(f"SELECT COUNT(*) AS n FROM {TABLE} WHERE {col} IS NULL")[
                "n"
            ].iloc[0]
        )
        status = "OK" if n_null == 0 else f"WARN: {n_null} nulls"
        print(f"  {col:<25} {status}")
        if n_null > 0:
            found_nulls = True

    print(f"\n{'='*52}")
    print(
        "Result:",
        "WARNING - nulls found" if found_nulls else "PASS - all checks passed",
    )
    print(f"{'='*52}\n")


if __name__ == "__main__":
    run_verification()
