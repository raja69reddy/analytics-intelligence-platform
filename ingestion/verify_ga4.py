"""
Verification script for raw_ga4_sessions data quality.

Usage:
    python ingestion/verify_ga4.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df

TABLE = "raw_ga4_sessions"


def run_verification() -> None:
    # Total row count
    df_count = query_df(f"SELECT COUNT(*) AS total FROM {TABLE}")
    total = df_count["total"].iloc[0]
    print(f"\n{'='*50}")
    print("  raw_ga4_sessions Verification Report")
    print(f"{'='*50}")
    print(f"\nTotal rows: {total:,}")

    # Date range
    df_dates = query_df(
        f"SELECT MIN(session_date) AS min_date, MAX(session_date) AS max_date FROM {TABLE}"
    )
    min_date = df_dates["min_date"].iloc[0]
    max_date = df_dates["max_date"].iloc[0]
    print(f"Date range: {min_date}  ->  {max_date}")

    # Top 5 channels by session count
    df_channels = query_df(f"""
        SELECT channel_grouping, SUM(sessions) AS total_sessions
        FROM {TABLE}
        GROUP BY channel_grouping
        ORDER BY total_sessions DESC
        LIMIT 5
    """)
    print("\nTop 5 channels by session count:")
    for _, row in df_channels.iterrows():
        print(
            f"  {row['channel_grouping']:<20} {int(row['total_sessions']):>8,} sessions"
        )

    # Null check for key columns
    key_cols = [
        "session_date",
        "source",
        "medium",
        "channel_grouping",
        "sessions",
        "pageviews",
    ]
    print("\nNull value check:")
    found_nulls = False
    for col in key_cols:
        df_null = query_df(f"SELECT COUNT(*) AS n FROM {TABLE} WHERE {col} IS NULL")
        n = int(df_null["n"].iloc[0])
        status = "OK" if n == 0 else f"WARN: {n} nulls"
        print(f"  {col:<25} {status}")
        if n > 0:
            found_nulls = True

    print(f"\n{'='*50}")
    if found_nulls:
        print("Result: WARNING - null values detected in key columns")
    else:
        print("Result: PASS - all checks passed")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run_verification()
