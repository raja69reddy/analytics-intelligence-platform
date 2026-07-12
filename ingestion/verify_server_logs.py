"""
Verification script for raw_server_logs data quality.

Usage:
    python ingestion/verify_server_logs.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df

TABLE = "raw_server_logs"


def run_verification() -> None:
    print(f"\n{'='*50}")
    print("  raw_server_logs Verification Report")
    print(f"{'='*50}")

    # Total row count
    df_count = query_df(f"SELECT COUNT(*) AS total FROM {TABLE}")
    total = int(df_count["total"].iloc[0])
    print(f"\nTotal rows: {total:,}")

    # Date range
    df_dates = query_df(f"""
        SELECT MIN(log_time)::date AS min_date,
               MAX(log_time)::date AS max_date
        FROM {TABLE}
    """)
    min_date = df_dates["min_date"].iloc[0]
    max_date = df_dates["max_date"].iloc[0]
    print(f"Date range: {min_date}  ->  {max_date}")

    # Top 5 URLs by request count
    df_urls = query_df(f"""
        SELECT url, COUNT(*) AS request_count
        FROM {TABLE}
        GROUP BY url
        ORDER BY request_count DESC
        LIMIT 5
    """)
    print("\nTop 5 URLs by request count:")
    for _, row in df_urls.iterrows():
        print(f"  {row['url']:<30} {int(row['request_count']):>6,} requests")

    # Status code distribution
    df_status = query_df(f"""
        SELECT status_code, COUNT(*) AS count
        FROM {TABLE}
        GROUP BY status_code
        ORDER BY status_code
    """)
    print("\nStatus code distribution:")
    for _, row in df_status.iterrows():
        code = int(row["status_code"])
        n = int(row["count"])
        bar = "#" * min(30, n // (total // 30 or 1))
        print(f"  {code}  {n:>6,}  {bar}")

    # Null check for key columns
    key_cols = ["log_time", "ip_address", "method", "url", "status_code"]
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
