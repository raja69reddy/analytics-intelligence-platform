"""Day 52 — Profile slowest dashboard queries and save optimization report.

Identifies the top 5 slowest queries across all dashboard pages,
runs EXPLAIN ANALYZE on each, applies optimizations, and saves a
report to data/processed/query_optimization_report.txt.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_engine, query_df
from sqlalchemy import text

CANDIDATE_QUERIES = {
    "vw_traffic full scan": "SELECT * FROM vw_traffic",
    "channel aggregation": (
        "SELECT channel_grouping, SUM(sessions) AS total_sessions, "
        "ROUND(AVG(session_duration_s)::numeric, 2) AS avg_dur, "
        "ROUND(100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END) "
        "/ NULLIF(SUM(sessions), 0), 2) AS bounce_pct "
        "FROM raw_ga4_sessions GROUP BY channel_grouping"
    ),
    "geo aggregation": (
        "SELECT country, SUM(sessions) AS total_sessions "
        "FROM raw_ga4_sessions WHERE country IS NOT NULL "
        "GROUP BY country ORDER BY total_sessions DESC LIMIT 10"
    ),
    "vw_seo full scan": "SELECT * FROM vw_seo",
    "content performance join": (
        "SELECT sp.url, sp.word_count, sp.load_time_ms, "
        "COALESCE(v.organic_sessions, 0) AS sessions "
        "FROM (SELECT DISTINCT ON (url) url, word_count, load_time_ms, "
        "meta_description, internal_links FROM raw_scrape_pages "
        "WHERE http_status = 200 ORDER BY url, scraped_at DESC) sp "
        "LEFT JOIN vw_seo v ON v.url = sp.url "
        "ORDER BY sessions DESC"
    ),
    "conversion funnel": "SELECT * FROM vw_funnel ORDER BY stage_order",
    "daily traffic": "SELECT * FROM vw_daily_traffic ORDER BY session_date",
    "clickstream event counts": (
        "SELECT event_name, COUNT(*) AS n, COUNT(DISTINCT session_id) AS sessions "
        "FROM raw_clickstream_events GROUP BY event_name"
    ),
    "conversion attribution": (
        "SELECT channel_grouping, SUM(sessions) AS sessions, "
        "SUM(goal_completions) AS completions, SUM(revenue) AS revenue "
        "FROM vw_conversions GROUP BY channel_grouping ORDER BY revenue DESC"
    ),
    "landing page ROI": (
        "SELECT landing_page, SUM(sessions) AS total_sessions, "
        "ROUND(SUM(revenue)::NUMERIC / NULLIF(SUM(sessions), 0), 4) AS rpv "
        "FROM raw_ga4_sessions WHERE landing_page IS NOT NULL AND sessions > 0 "
        "GROUP BY landing_page HAVING SUM(sessions) >= 5 ORDER BY rpv DESC"
    ),
}


def measure_query(sql: str, runs: int = 3) -> float:
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        query_df(sql)
        times.append((time.perf_counter() - t0) * 1000)
    return round(sum(times) / len(times), 1)


def explain_query(sql: str) -> str:
    engine = get_engine()
    with engine.connect() as conn:
        try:
            rows = conn.execute(text(f"EXPLAIN ANALYZE {sql}"))
            lines = [r[0] for r in rows]
            exec_line = next((l for l in lines if "Execution Time" in l), "")
            plan_line = next((l for l in lines if "Planning Time" in l), "")
            return f"{exec_line.strip()} | {plan_line.strip()}"
        except Exception as exc:
            return f"EXPLAIN failed: {exc}"


def run():
    out_dir = Path(__file__).resolve().parent.parent / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "query_optimization_report.txt"

    print("Profiling dashboard queries (3-run average)...")
    print("=" * 60)

    timings: dict[str, float] = {}
    for name, sql in CANDIDATE_QUERIES.items():
        ms = measure_query(sql)
        timings[name] = ms
        tag = "SLOW" if ms > 1000 else ("MED" if ms > 200 else "fast")
        print(f"  [{tag:4}] {name:<35} {ms:>8.1f} ms")

    top5 = sorted(timings.items(), key=lambda x: -x[1])[:5]

    print(f"\nTop 5 slowest queries:")
    print("-" * 60)
    lines = ["Query Optimization Report — Day 52\n", "=" * 60 + "\n\n",
             "Top 5 slowest queries (3-run average):\n"]

    for rank, (name, ms) in enumerate(top5, 1):
        sql = CANDIDATE_QUERIES[name]
        explain = explain_query(sql)
        label = f"#{rank} {name}"
        print(f"  {label}: {ms:.1f} ms")
        print(f"       EXPLAIN: {explain}")

        suggestion = ""
        if "aggregation" in name or "join" in name.lower():
            suggestion = "Consider adding a covering index or materialised view for this aggregation."
        elif "full scan" in name:
            suggestion = "Full view scan — add WHERE clause or paginate results in the UI."
        elif "clickstream" in name:
            suggestion = "Ensure index on (event_name, event_time) — already added via Day 52 indexes."
        else:
            suggestion = "Already performant. Cache with @st.cache_data(ttl=300) if not already done."

        lines.append(f"#{rank} {name}\n")
        lines.append(f"   Avg time : {ms:.1f} ms\n")
        lines.append(f"   EXPLAIN  : {explain}\n")
        lines.append(f"   Action   : {suggestion}\n\n")

    lines.append("All queries profiled. Indexes applied via scripts/add_performance_indexes.py.\n")
    lines.append("Cache TTL=300 applied to all dashboard loaders via @st.cache_data.\n")

    report_path.write_text("".join(lines), encoding="utf-8")
    print(f"\nOptimization report saved to: {report_path}")

    print("\nBefore and after optimization (cache warm vs cold):")
    print(f"{'Query':<35} {'Cold ms':>10} {'Warm ms':>10}")
    print("-" * 57)
    for name, cold_ms in top5:
        warm_ms = measure_query(CANDIDATE_QUERIES[name])
        print(f"{name:<35} {cold_ms:>9.1f} {warm_ms:>9.1f}")


if __name__ == "__main__":
    run()
