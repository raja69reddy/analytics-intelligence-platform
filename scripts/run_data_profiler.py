"""Day 53 — Run data profiler on all 4 raw tables and save reports.

Profiles raw_ga4_sessions, raw_server_logs, raw_scrape_pages, and
raw_clickstream_events; saves JSON reports to data/processed/profiles/.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df
from utils.data_profiler import save_profile_report, profile_dataframe

TABLES = {
    "ga4_sessions": "SELECT * FROM raw_ga4_sessions",
    "server_logs": "SELECT * FROM raw_server_logs",
    "scrape_pages": "SELECT * FROM raw_scrape_pages",
    "clickstream_events": "SELECT * FROM raw_clickstream_events",
}


def run() -> None:
    print("=" * 62)
    print("  Data Profiler — Day 53")
    print("=" * 62)

    for name, sql in TABLES.items():
        print(f"\n  Profiling {name}...")
        t0 = time.perf_counter()
        df = query_df(sql)
        profile = profile_dataframe(df, name=name)
        path = save_profile_report(df, name=name)
        elapsed = time.perf_counter() - t0

        q = profile["quality"]
        score = q["score"]
        score_tag = "GOOD" if score >= 80 else ("WARN" if score >= 60 else "POOR")

        print(f"    Rows          : {profile['row_count']:>10,}")
        print(f"    Columns       : {profile['column_count']:>10}")
        print(f"    Quality score : {score:>9.1f}  [{score_tag}]")
        print(f"    Avg null %    : {q['avg_null_pct']:>9.2f}%")
        print(f"    Duplicate %   : {q['duplicate_pct']:>9.2f}%")
        print(f"    Avg outlier % : {q['avg_outlier_pct']:>9.2f}%")

        if q["cols_with_nulls"] > 0:
            null_cols = [
                col
                for col, v in profile["null_summary"].items()
                if v["null_count"] > 0
            ]
            print(f"    Null columns  : {', '.join(null_cols)}")

        if profile["outlier_summary"]:
            top_outlier = max(
                profile["outlier_summary"].items(),
                key=lambda x: x[1]["outlier_pct"],
            )
            print(f"    Top outlier   : {top_outlier[0]} ({top_outlier[1]['outlier_pct']}%)")

        print(f"    Report saved  : {path.name}  ({elapsed:.1f}s)")

    print("\n" + "=" * 62)
    print("  All 4 profile reports saved to data/processed/profiles/")
    print("=" * 62)


if __name__ == "__main__":
    run()
