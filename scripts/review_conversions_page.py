"""Day 51 — Conversions page end-to-end review."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df


def run():
    checks = [
        ("vw_conversions", "SELECT * FROM vw_conversions LIMIT 20"),
        ("vw_funnel (waterfall)", "SELECT * FROM vw_funnel ORDER BY stage_order"),
        (
            "CVR trend",
            "SELECT session_date, "
            "ROUND(SUM(goal_completions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS cvr_pct "
            "FROM vw_conversions GROUP BY session_date ORDER BY session_date LIMIT 30",
        ),
        (
            "Channel conversions",
            "SELECT channel_grouping, SUM(sessions) AS sessions, "
            "SUM(goal_completions) AS goal_completions, SUM(revenue) AS revenue "
            "FROM vw_conversions GROUP BY channel_grouping",
        ),
        (
            "Micro conversions",
            "SELECT event_name, COUNT(*) AS event_count, "
            "COUNT(DISTINCT session_id) AS unique_sessions "
            "FROM raw_clickstream_events GROUP BY event_name",
        ),
        (
            "Conversion time by hour",
            "SELECT EXTRACT(HOUR FROM event_time) AS hour_of_day, COUNT(*) AS n "
            "FROM raw_clickstream_events WHERE event_name = 'form_submit' "
            "GROUP BY hour_of_day ORDER BY hour_of_day",
        ),
        (
            "Conversion time by day of week",
            "SELECT EXTRACT(DOW FROM event_time) AS dow, COUNT(*) AS n "
            "FROM raw_clickstream_events WHERE event_name = 'form_submit' "
            "GROUP BY dow ORDER BY dow",
        ),
        (
            "Sankey page flow",
            """WITH entry_pages AS (
                SELECT session_id, MIN(event_time) AS entry_time,
                       MIN(page_url) AS entry_page
                FROM raw_clickstream_events GROUP BY session_id
            ),
            conv_pages AS (
                SELECT session_id, page_url AS conv_page
                FROM raw_clickstream_events WHERE event_name = 'form_submit'
            )
            SELECT ep.entry_page AS source_page, cp.conv_page AS target_page,
                   COUNT(*) AS conversions
            FROM entry_pages ep JOIN conv_pages cp ON cp.session_id = ep.session_id
            WHERE ep.entry_page != cp.conv_page
            GROUP BY ep.entry_page, cp.conv_page ORDER BY conversions DESC LIMIT 10""",
        ),
        (
            "Goal trend by channel",
            "SELECT session_date, channel_grouping, SUM(goal_completions) AS g "
            "FROM vw_conversions GROUP BY session_date, channel_grouping "
            "ORDER BY session_date LIMIT 20",
        ),
        (
            "Attribution first touch",
            "SELECT channel_grouping, SUM(sessions) AS sessions "
            "FROM raw_ga4_sessions GROUP BY channel_grouping",
        ),
        (
            "Revenue by channel",
            "SELECT channel_grouping, SUM(revenue) AS revenue FROM vw_conversions "
            "GROUP BY channel_grouping ORDER BY revenue DESC",
        ),
    ]

    all_ok = True
    print("Conversions page end-to-end review")
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
        print("Conversions page review: PASSED")
    else:
        print("Conversions page review: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    run()
