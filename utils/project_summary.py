"""
Project summary: prints an overview of all tables, views, tests, and data ranges.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.db import query_df  # noqa: E402

RAW_TABLES = [
    "raw_ga4_sessions",
    "raw_server_logs",
    "raw_clickstream_events",
    "raw_scrape_pages",
]
FACT_DIM_TABLES = [
    "fct_sessions",
    "fct_events",
    "dim_dates",
    "dim_pages",
]


def _count(table: str) -> int:
    try:
        return int(query_df(f"SELECT COUNT(*) AS n FROM {table}")["n"].iloc[0])
    except Exception:
        return -1


def _date_range(table: str, col: str) -> tuple[str, str]:
    try:
        df = query_df(
            f"SELECT MIN({col})::date AS mn, MAX({col})::date AS mx FROM {table}"
        )
        return str(df["mn"].iloc[0]), str(df["mx"].iloc[0])
    except Exception:
        return "N/A", "N/A"


def _last_ingested(table: str) -> str:
    try:
        df = query_df(f"SELECT MAX(ingested_at) AS ts FROM {table}")
        ts = df["ts"].iloc[0]
        return str(ts)[:19] if ts else "never"
    except Exception:
        return "N/A"


def _view_count() -> int:
    try:
        df = query_df(
            "SELECT COUNT(*) AS n FROM information_schema.views "
            "WHERE table_schema = 'public'"
        )
        return int(df["n"].iloc[0])
    except Exception:
        return -1


def _test_count() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--co", "-q", "--tb=no"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    for line in reversed(result.stdout.splitlines()):
        if (
            "test" in line.lower()
            or "selected" in line.lower()
            or "item" in line.lower()
        ):
            return line.strip()
    return "unknown"


def run_summary() -> None:
    print()
    print("=" * 64)
    print("  PROJECT SUMMARY — web_analytics")
    print("=" * 64)

    # Raw tables
    print("\n  RAW TABLES")
    print("  " + "-" * 58)
    date_cols = {
        "raw_ga4_sessions": "session_date",
        "raw_server_logs": "log_time",
        "raw_clickstream_events": "event_time",
        "raw_scrape_pages": "scraped_at",
    }
    for t in RAW_TABLES:
        rows = _count(t)
        mn, mx = _date_range(t, date_cols[t])
        last = _last_ingested(t)
        print(f"  {t:<32} {rows:>6,} rows  |  {mn} -> {mx}")
        print(f"  {'  last ingested':<32} {last}")

    # Fact / dim tables
    print("\n  DIMENSION / FACT TABLES")
    print("  " + "-" * 58)
    for t in FACT_DIM_TABLES:
        rows = _count(t)
        status = f"{rows:>6,} rows" if rows >= 0 else "  (table empty or missing)"
        print(f"  {t:<32} {status}")

    # SQL views
    n_views = _view_count()
    print("\n  SQL VIEWS")
    print("  " + "-" * 58)
    print(f"  {'Total views in public schema':<32} {n_views:>6}")

    # Tests
    test_line = _test_count()
    print("\n  TEST SUITE")
    print("  " + "-" * 58)
    print(f"  {test_line}")

    print()
    print("=" * 64)
    print()


if __name__ == "__main__":
    run_summary()
