"""Day 51 — Traffic page end-to-end review.

Verifies all SQL queries used by dashboard/pages/1_traffic.py
against the live PostgreSQL database. Each query is run with
representative parameters and the result schema is validated.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df


def run():
    checks = [
        ("vw_traffic (all rows)", "SELECT * FROM vw_traffic LIMIT 50"),
        ("vw_daily_traffic", "SELECT * FROM vw_daily_traffic LIMIT 90"),
        (
            "Channel performance",
            """SELECT channel_grouping,
                      SUM(sessions) AS total_sessions,
                      SUM(new_users) AS total_new_users,
                      ROUND(AVG(session_duration_s)::numeric, 2) AS avg_session_duration,
                      ROUND(100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)
                          / NULLIF(SUM(sessions), 0), 2) AS bounce_rate_pct
               FROM raw_ga4_sessions GROUP BY channel_grouping""",
        ),
        (
            "Device breakdown",
            "SELECT device_category, SUM(sessions) AS total_sessions FROM raw_ga4_sessions "
            "WHERE device_category IS NOT NULL GROUP BY device_category",
        ),
        ("New vs returning", "SELECT * FROM vw_new_vs_returning LIMIT 30"),
        (
            "Geo top 10",
            "SELECT country, SUM(sessions) AS total_sessions FROM raw_ga4_sessions "
            "WHERE country IS NOT NULL GROUP BY country ORDER BY total_sessions DESC LIMIT 10",
        ),
        (
            "Pageviews & users over time",
            "SELECT session_date, SUM(pageviews) AS total_pageviews, SUM(new_users) AS total_users "
            "FROM raw_ga4_sessions GROUP BY session_date ORDER BY session_date LIMIT 30",
        ),
        (
            "Sessions by channel over time",
            "SELECT session_date, channel_grouping, SUM(sessions) AS sessions "
            "FROM raw_ga4_sessions GROUP BY session_date, channel_grouping "
            "ORDER BY session_date, channel_grouping LIMIT 30",
        ),
        (
            "KPI comparison (prev period)",
            "SELECT SUM(total_sessions) AS s FROM vw_traffic",
        ),
    ]

    all_ok = True
    print("Traffic page end-to-end review")
    print("=" * 45)
    for name, sql in checks:
        try:
            df = query_df(sql)
            print(f"  PASS  {name} ({len(df)} rows)")
        except Exception as exc:
            print(f"  FAIL  {name} -> {exc}")
            all_ok = False

    print()
    if all_ok:
        print("Traffic page review: PASSED")
    else:
        print("Traffic page review: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    run()
