"""Day 55 — Profile all dashboard page queries using EXPLAIN ANALYZE.

Profiles 5 representative queries per dashboard page (traffic, behavior,
conversions, SEO), prints a ranked slowest-first table, and saves results
to data/processed/query_profiles.csv.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sql.optimization.query_profiler import print_profile, save_profile_results, PROFILES_CSV

# ── Query definitions per page ────────────────────────────────────────────────

TRAFFIC_QUERIES = [
    (
        "traffic/daily_sessions",
        "SELECT session_date, SUM(sessions) AS sessions, SUM(new_users) AS new_users "
        "FROM raw_ga4_sessions GROUP BY session_date ORDER BY session_date",
    ),
    (
        "traffic/channel_breakdown",
        "SELECT channel_grouping, SUM(sessions) AS sessions, "
        "SUM(conversions) AS conversions "
        "FROM raw_ga4_sessions GROUP BY channel_grouping ORDER BY sessions DESC",
    ),
    (
        "traffic/vw_traffic_full",
        "SELECT * FROM vw_traffic",
    ),
    (
        "traffic/vw_daily_traffic",
        "SELECT * FROM vw_daily_traffic",
    ),
    (
        "traffic/vw_channel_performance",
        "SELECT * FROM vw_channel_performance",
    ),
]

BEHAVIOR_QUERIES = [
    (
        "behavior/vw_behavior",
        "SELECT * FROM vw_behavior",
    ),
    (
        "behavior/vw_top_pages",
        "SELECT * FROM vw_top_pages",
    ),
    (
        "behavior/scroll_depth",
        "SELECT event_name, ROUND(AVG(scroll_depth_pct)::numeric, 2) AS avg_scroll, "
        "COUNT(*) AS events "
        "FROM raw_clickstream_events WHERE event_name = 'scroll' "
        "GROUP BY event_name",
    ),
    (
        "behavior/event_breakdown",
        "SELECT event_name, COUNT(*) AS total_events, "
        "COUNT(DISTINCT session_id) AS unique_sessions "
        "FROM raw_clickstream_events GROUP BY event_name ORDER BY total_events DESC",
    ),
    (
        "behavior/page_response_time",
        "SELECT url, ROUND(AVG(response_time_ms)::numeric, 1) AS avg_ms, COUNT(*) AS hits "
        "FROM raw_server_logs "
        "GROUP BY url ORDER BY avg_ms DESC LIMIT 20",
    ),
]

CONVERSION_QUERIES = [
    (
        "conversions/vw_conversions",
        "SELECT * FROM vw_conversions",
    ),
    (
        "conversions/vw_funnel",
        "SELECT * FROM vw_funnel",
    ),
    (
        "conversions/conversion_rate",
        "SELECT channel_grouping, "
        "SUM(conversions) AS conversions, SUM(sessions) AS sessions, "
        "ROUND(100.0 * SUM(conversions) / NULLIF(SUM(sessions), 0), 2) AS conv_rate "
        "FROM raw_ga4_sessions GROUP BY channel_grouping ORDER BY conv_rate DESC",
    ),
    (
        "conversions/daily_revenue",
        "SELECT session_date, SUM(revenue) AS revenue, SUM(conversions) AS conversions "
        "FROM raw_ga4_sessions GROUP BY session_date ORDER BY session_date",
    ),
    (
        "conversions/device_conversion",
        "SELECT device_category, SUM(sessions) AS sessions, "
        "SUM(conversions) AS conversions, "
        "ROUND(100.0 * SUM(conversions) / NULLIF(SUM(sessions), 0), 2) AS conv_rate "
        "FROM raw_ga4_sessions GROUP BY device_category",
    ),
]

SEO_QUERIES = [
    (
        "seo/vw_seo",
        "SELECT * FROM vw_seo",
    ),
    (
        "seo/word_count_dist",
        "SELECT "
        "CASE WHEN word_count < 300 THEN 'thin (<300)' "
        "     WHEN word_count < 1000 THEN 'medium (300-1000)' "
        "     ELSE 'long (1000+)' END AS content_tier, "
        "COUNT(*) AS pages, ROUND(AVG(word_count)::numeric, 0) AS avg_words "
        "FROM raw_scrape_pages GROUP BY 1 ORDER BY avg_words",
    ),
    (
        "seo/load_time_analysis",
        "SELECT url, load_time_ms, word_count, http_status "
        "FROM raw_scrape_pages ORDER BY load_time_ms DESC LIMIT 10",
    ),
    (
        "seo/http_status_breakdown",
        "SELECT http_status, COUNT(*) AS pages "
        "FROM raw_scrape_pages GROUP BY http_status ORDER BY pages DESC",
    ),
    (
        "seo/error_pages",
        "SELECT url, status_code, COUNT(*) AS hits "
        "FROM raw_server_logs WHERE status_code >= 400 "
        "GROUP BY url, status_code ORDER BY hits DESC LIMIT 15",
    ),
]

ALL_PAGES = [
    ("Traffic",     TRAFFIC_QUERIES),
    ("Behavior",    BEHAVIOR_QUERIES),
    ("Conversions", CONVERSION_QUERIES),
    ("SEO",         SEO_QUERIES),
]


def run() -> None:
    print("=" * 70)
    print("  Day 55 — Dashboard Query Profiler")
    print("=" * 70)

    all_results: list[dict] = []

    for page_name, queries in ALL_PAGES:
        print(f"\n{'-' * 70}")
        print(f"  {page_name.upper()} PAGE")
        print(f"{'-' * 70}")
        for label, sql in queries:
            try:
                result = print_profile(label, sql, runs=3)
                all_results.append(result)
            except Exception as exc:
                print(f"  [{label}] ERROR: {exc}")
                all_results.append({"label": label, "avg_ms": -1, "pg_exec_ms": -1,
                                     "sql_preview": sql[:80]})

    # Save
    out_path = save_profile_results(all_results)

    # Ranked summary
    ranked = sorted(
        [r for r in all_results if r.get("avg_ms", -1) >= 0],
        key=lambda r: -r["avg_ms"],
    )

    print("\n" + "=" * 70)
    print("  RANKED: SLOWEST QUERIES (wall-clock avg)")
    print("=" * 70)
    print(f"  {'Rank':<5} {'Label':<40} {'Wall ms':>10}  {'PG ms':>10}")
    print("  " + "-" * 66)
    for i, r in enumerate(ranked, 1):
        pg_ms = r.get("pg_exec_ms", -1)
        pg_str = f"{pg_ms:.2f}" if pg_ms >= 0 else "n/a"
        print(f"  {i:<5} {r['label']:<40} {r['avg_ms']:>9.1f}  {pg_str:>10}")

    print("=" * 70)
    print(f"\n  Results saved to: {out_path}")
    print(f"  Total queries profiled: {len(all_results)}")


if __name__ == "__main__":
    run()
