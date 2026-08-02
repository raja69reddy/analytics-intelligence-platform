"""Day 51 — Behavior page end-to-end review."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df


def run():
    checks = [
        ("vw_behavior", "SELECT * FROM vw_behavior LIMIT 10"),
        ("vw_top_pages", "SELECT * FROM vw_top_pages LIMIT 10"),
        ("vw_scroll_depth", "SELECT * FROM vw_scroll_depth LIMIT 10"),
        ("vw_engagement_events", "SELECT * FROM vw_engagement_events LIMIT 10"),
        ("vw_funnel", "SELECT * FROM vw_funnel ORDER BY stage_order"),
        ("vw_new_vs_returning", "SELECT * FROM vw_new_vs_returning LIMIT 30"),
        (
            "Avg time on page",
            "SELECT channel_grouping, AVG(session_duration_s) AS avg_s "
            "FROM raw_ga4_sessions GROUP BY channel_grouping",
        ),
        (
            "Bounce trend",
            "SELECT session_date, "
            "ROUND(100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)"
            " / NULLIF(SUM(sessions), 0), 2) AS bounce_rate_pct "
            "FROM raw_ga4_sessions GROUP BY session_date ORDER BY session_date LIMIT 30",
        ),
        (
            "Page paths",
            "SELECT page_url, session_id, event_time FROM raw_clickstream_events "
            "WHERE event_name = 'pageview' ORDER BY session_id, event_time LIMIT 20",
        ),
        (
            "Top pages by events",
            "SELECT page_url, COUNT(*) AS total_events "
            "FROM raw_clickstream_events GROUP BY page_url "
            "ORDER BY total_events DESC LIMIT 10",
        ),
        (
            "Session quality",
            "SELECT channel_grouping, AVG(sessions) AS avg_sessions, "
            "AVG(conversions) AS avg_conv FROM raw_ga4_sessions GROUP BY channel_grouping",
        ),
        (
            "Event trend",
            "SELECT DATE(event_time) AS event_date, event_name, COUNT(*) AS n "
            "FROM raw_clickstream_events GROUP BY event_date, event_name "
            "ORDER BY event_date LIMIT 20",
        ),
        (
            "DAU / MAU",
            "SELECT COUNT(DISTINCT session_date) AS dau FROM raw_ga4_sessions "
            "WHERE session_date >= CURRENT_DATE - 30",
        ),
        (
            "Scroll depth dated filter",
            "SELECT page_url, avg_scroll_depth_pct FROM vw_scroll_depth LIMIT 5",
        ),
        (
            "Funnel dated",
            "SELECT stage_name, users_reached, drop_off_pct FROM vw_funnel ORDER BY stage_order",
        ),
    ]

    all_ok = True
    print("Behavior page end-to-end review")
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
        print("Behavior page review: PASSED")
    else:
        print("Behavior page review: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    run()
