"""
Data quality report for all raw tables in the web_analytics database.
Checks null counts, duplicate counts, date ranges, and row counts.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.db import query_df  # noqa: E402

# Table config: (table_name, date_column, pk_columns_for_dup_check)
RAW_TABLES = [
    ("raw_ga4_sessions", "session_date", ["id"]),
    ("raw_server_logs", "log_time", ["id"]),
    ("raw_clickstream_events", "event_time", ["id"]),
    ("raw_scrape_pages", "scraped_at", ["url"]),
]

# Key columns to check for NULLs per table
NULL_COLS = {
    "raw_ga4_sessions": ["session_date", "channel_grouping", "sessions", "pageviews"],
    "raw_server_logs": ["log_time", "ip_address", "url", "status_code"],
    "raw_clickstream_events": ["event_time", "session_id", "event_name", "page_url"],
    "raw_scrape_pages": ["url", "scraped_at", "word_count"],
}


def _row_count(table: str) -> int:
    return int(query_df(f"SELECT COUNT(*) AS n FROM {table}")["n"].iloc[0])


def _null_counts(table: str) -> dict[str, int]:
    cols = NULL_COLS.get(table, [])
    result = {}
    for col in cols:
        n = int(
            query_df(f"SELECT COUNT(*) AS n FROM {table} WHERE {col} IS NULL")[
                "n"
            ].iloc[0]
        )
        result[col] = n
    return result


def _duplicate_count(table: str, pk_cols: list[str]) -> int:
    pk_expr = ", ".join(pk_cols)
    df = query_df(
        f"SELECT COUNT(*) AS n FROM ("
        f"  SELECT {pk_expr}, COUNT(*) AS c FROM {table} GROUP BY {pk_expr} HAVING COUNT(*) > 1"
        f") AS dups"
    )
    return int(df["n"].iloc[0])


def _date_range(table: str, date_col: str) -> tuple[str, str]:
    df = query_df(
        f"SELECT MIN({date_col})::date AS mn, MAX({date_col})::date AS mx FROM {table}"
    )
    mn = str(df["mn"].iloc[0])
    mx = str(df["mx"].iloc[0])
    return mn, mx


def run_report() -> None:
    print()
    print("=" * 64)
    print("  DATA QUALITY REPORT — web_analytics")
    print("=" * 64)

    all_pass = True

    for table, date_col, pk_cols in RAW_TABLES:
        print(f"\n  Table: {table}")
        print("  " + "-" * 58)

        # Row count
        rows = _row_count(table)
        print(f"  {'Row count':<28} {rows:>10,}")

        # Date range
        mn, mx = _date_range(table, date_col)
        print(f"  {'Date range':<28} {mn}  ->  {mx}")

        # Nulls
        nulls = _null_counts(table)
        null_issues = {col: n for col, n in nulls.items() if n > 0}
        if null_issues:
            all_pass = False
            for col, n in null_issues.items():
                print(f"  {'NULL ' + col:<28} {n:>10,}  [FAIL]")
        else:
            null_label = ", ".join(NULL_COLS.get(table, []))
            print(f"  {'Nulls (' + null_label[:24] + '...)':<28} {'OK':>10}")

        # Duplicates
        dup_count = _duplicate_count(table, pk_cols)
        if dup_count > 0:
            all_pass = False
            print(f"  {'Duplicate rows':<28} {dup_count:>10,}  [FAIL]")
        else:
            print(f"  {'Duplicate rows':<28} {'0 (OK)':>10}")

    print()
    print("=" * 64)
    if all_pass:
        print("  RESULT: PASS — all quality checks passed")
    else:
        print("  RESULT: FAIL — see issues above")
    print("=" * 64)
    print()


if __name__ == "__main__":
    run_report()
