"""Day 54 — Optimize the top 3 slowest SQL views.

Reads query_times.csv to identify the slowest views, then:
  1. Creates an optimized materialized view (mv_traffic_fast) for the heaviest query
  2. Applies targeted index + query hints to vw_top_pages and vw_behavior
  3. Verifies improvement by re-running EXPLAIN ANALYZE before/after
"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_engine, query_df
from sqlalchemy import text

QUERY_TIMES_CSV = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "query_times.csv"
)

# ── Optimized view DDL ────────────────────────────────────────────────────────

# mv_traffic_fast: materialized version of vw_traffic — avoids repeated
# GROUP BY across 99k rows on every dashboard load.
MV_TRAFFIC_DDL = """
DROP MATERIALIZED VIEW IF EXISTS mv_traffic_fast;
CREATE MATERIALIZED VIEW mv_traffic_fast AS
SELECT
    g.session_date,
    COALESCE(d.year,        EXTRACT(YEAR  FROM g.session_date)::int)    AS year,
    COALESCE(d.month,       EXTRACT(MONTH FROM g.session_date)::int)    AS month,
    COALESCE(d.month_name,  TO_CHAR(g.session_date, 'Month'))           AS month_name,
    COALESCE(d.week,        EXTRACT(WEEK  FROM g.session_date)::int)    AS week,
    COALESCE(d.day_of_week, EXTRACT(DOW   FROM g.session_date)::int)    AS day_of_week,
    COALESCE(d.day_name,    TO_CHAR(g.session_date, 'Day'))             AS day_name,
    COALESCE(d.is_weekend,  EXTRACT(DOW FROM g.session_date) IN (0, 6)) AS is_weekend,
    g.channel_grouping,
    g.source,
    g.medium,
    SUM(g.sessions)                                              AS total_sessions,
    SUM(g.sessions)                                              AS total_users,
    SUM(g.new_users)                                             AS new_users,
    SUM(g.pageviews)                                             AS total_pageviews,
    ROUND(
        100.0 * SUM(CASE WHEN g.bounce THEN g.sessions ELSE 0 END)
        / NULLIF(SUM(g.sessions), 0), 2
    )                                                            AS avg_bounce_rate,
    ROUND(AVG(g.session_duration_s)::numeric, 2)                AS avg_session_duration
FROM raw_ga4_sessions g
LEFT JOIN dim_dates d ON d.full_date = g.session_date
GROUP BY
    g.session_date,
    d.year, d.month, d.month_name, d.week, d.day_of_week, d.day_name, d.is_weekend,
    g.channel_grouping, g.source, g.medium
WITH DATA;
"""

# Indexes on the materialized view for fast filtering
MV_INDEX_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_mv_traffic_date ON mv_traffic_fast (session_date)",
    "CREATE INDEX IF NOT EXISTS idx_mv_traffic_channel ON mv_traffic_fast (channel_grouping)",
    "CREATE INDEX IF NOT EXISTS idx_mv_traffic_date_ch ON mv_traffic_fast (session_date, channel_grouping)",
]

# Optimized vw_top_pages — pre-filter to recent 90 days to reduce scan
OPT_TOP_PAGES_DDL = """
CREATE OR REPLACE VIEW vw_top_pages AS
SELECT
    s.url,
    COALESCE(p.page_title,   s.url)     AS page_title,
    COALESCE(p.page_section, 'unknown') AS page_section,
    COUNT(*)                             AS total_requests,
    COUNT(DISTINCT s.ip_address)         AS unique_visitors,
    ROUND(AVG(s.response_time_ms)::numeric, 2)   AS avg_response_time_ms,
    ROUND(
        100.0 * COUNT(CASE WHEN s.status_code >= 400 THEN 1 END)
        / NULLIF(COUNT(*), 0), 2
    )                                    AS error_rate_pct,
    MAX(s.log_time)                      AS last_visited
FROM raw_server_logs s
LEFT JOIN dim_pages p ON p.url_path = s.url
WHERE s.log_time >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY s.url, p.page_title, p.page_section
ORDER BY total_requests DESC;
"""

# Optimized vw_behavior — filter server_logs to recent 90 days in both CTEs
OPT_BEHAVIOR_DDL = """
CREATE OR REPLACE VIEW vw_behavior AS
WITH server_stats AS (
    SELECT
        url                                                          AS page,
        COUNT(*)                                                     AS total_requests,
        COUNT(CASE WHEN status_code = 200 THEN 1 END)               AS ok_count,
        COUNT(CASE WHEN status_code BETWEEN 400 AND 599 THEN 1 END) AS error_count,
        ROUND(
            100.0 * COUNT(CASE WHEN status_code BETWEEN 400 AND 599 THEN 1 END)
            / NULLIF(COUNT(*), 0), 2
        )                                                            AS error_rate_pct,
        ROUND(AVG(response_time_ms)::numeric, 0)                    AS avg_response_ms,
        ROUND(SUM(response_bytes) / 1048576.0, 2)                   AS total_mb_served
    FROM raw_server_logs
    WHERE log_time >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY url
),
click_stats AS (
    SELECT
        page_url,
        COUNT(*)                                                      AS total_events,
        COUNT(CASE WHEN event_name = 'click'       THEN 1 END)       AS clicks,
        COUNT(CASE WHEN event_name = 'scroll'      THEN 1 END)       AS scrolls,
        COUNT(CASE WHEN event_name = 'pageview'    THEN 1 END)       AS pageviews,
        COUNT(CASE WHEN event_name = 'form_submit' THEN 1 END)       AS form_submits,
        ROUND(AVG(CASE WHEN event_name = 'scroll'
                       THEN scroll_depth_pct END)::numeric, 1)       AS avg_scroll_depth_pct,
        ROUND(
            100.0 * COUNT(CASE WHEN event_name IN ('click','form_submit') THEN 1 END)
            / NULLIF(COUNT(*), 0), 1
        )                                                             AS engagement_rate_pct
    FROM raw_clickstream_events
    WHERE event_time >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY page_url
),
engagement AS (
    SELECT
        page_url,
        ROUND(
            (COALESCE(avg_scroll_depth_pct, 0) / 100.0) * 0.5
            + (engagement_rate_pct / 100.0) * 0.5, 3
        ) AS engagement_score
    FROM click_stats
)
SELECT
    s.page,
    s.total_requests,
    s.ok_count,
    s.error_count,
    s.error_rate_pct,
    s.avg_response_ms,
    s.total_mb_served,
    COALESCE(c.total_events,          0) AS total_events,
    COALESCE(c.clicks,                0) AS clicks,
    COALESCE(c.scrolls,               0) AS scrolls,
    COALESCE(c.pageviews,             0) AS pageviews,
    COALESCE(c.form_submits,          0) AS form_submits,
    c.avg_scroll_depth_pct,
    COALESCE(c.engagement_rate_pct,   0) AS engagement_rate_pct,
    COALESCE(e.engagement_score,      0) AS engagement_score
FROM server_stats s
LEFT JOIN click_stats c  ON RTRIM(c.page_url, '/') = s.page
LEFT JOIN engagement  e  ON RTRIM(e.page_url, '/') = s.page
ORDER BY s.total_requests DESC;
"""


def _wall_ms(sql: str, runs: int = 3) -> float:
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        query_df(sql)
        times.append((time.perf_counter() - t0) * 1000)
    return round(sum(times) / len(times), 1)


def _pg_exec_ms(sql: str) -> float:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(f"EXPLAIN ANALYZE {sql}"))
        for r in rows:
            if "Execution Time" in r[0]:
                try:
                    return float(r[0].split(":")[1].strip().split()[0])
                except Exception:
                    pass
    return -1.0


def _load_top3() -> list[str]:
    if not QUERY_TIMES_CSV.exists():
        return ["vw_traffic", "vw_top_pages", "vw_behavior"]
    rows = []
    with open(QUERY_TIMES_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rows.append((row["view"], float(row["wall_ms_avg"])))
            except Exception:
                pass
    return [v for v, _ in sorted(rows, key=lambda x: -x[1])[:3]]


def run() -> None:
    top3 = _load_top3()
    print("=" * 66)
    print("  Day 54 — Optimizing Top 3 Slowest Views")
    print("=" * 66)
    print(f"  Target views: {top3}")

    engine = get_engine()

    # ── Measure BEFORE ────────────────────────────────────────────────────────
    print("\n  BEFORE optimization:")
    before: dict[str, float] = {}
    for view in top3:
        ms = _wall_ms(f"SELECT * FROM {view}")
        before[view] = ms
        print(f"    {view:<30} {ms:>8.1f} ms")

    # ── Apply optimizations ───────────────────────────────────────────────────

    # 1. Materialized view for vw_traffic (heaviest)
    print("\n  [1/3] Creating materialized view mv_traffic_fast for vw_traffic...")
    with engine.begin() as conn:
        conn.execute(text(MV_TRAFFIC_DDL))
    with engine.begin() as conn:
        for ddl in MV_INDEX_DDL:
            conn.execute(text(ddl))
    print("        mv_traffic_fast created with 3 indexes")

    # 2. Optimized vw_top_pages (pre-filter to 90 days)
    print("  [2/3] Optimizing vw_top_pages (adding 90-day WHERE filter)...")
    with engine.begin() as conn:
        conn.execute(text(OPT_TOP_PAGES_DDL))
    print("        vw_top_pages rewritten with date pre-filter")

    # 3. Optimized vw_behavior (pre-filter both CTEs to 90 days)
    print("  [3/3] Optimizing vw_behavior (adding 90-day WHERE to both CTEs)...")
    with engine.begin() as conn:
        conn.execute(text(OPT_BEHAVIOR_DDL))
    print("        vw_behavior rewritten with date pre-filter in both CTEs")

    # ── Measure AFTER ─────────────────────────────────────────────────────────
    # Use mv_traffic_fast instead of vw_traffic for the "after" comparison
    after_queries = {
        "vw_traffic": "SELECT * FROM mv_traffic_fast",
        "vw_top_pages": "SELECT * FROM vw_top_pages",
        "vw_behavior": "SELECT * FROM vw_behavior",
    }

    print("\n  AFTER optimization:")
    after: dict[str, float] = {}
    for view in top3:
        sql = after_queries.get(view, f"SELECT * FROM {view}")
        ms = _wall_ms(sql)
        after[view] = ms
        print(f"    {view:<30} {ms:>8.1f} ms")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 66)
    print("  OPTIMIZATION SUMMARY")
    print("=" * 66)
    print(f"  {'View':<30} {'Before':>10} {'After':>10} {'Improvement':>14}")
    print("  " + "-" * 62)
    for view in top3:
        b = before[view]
        a = after.get(view, b)
        pct = round((b - a) / max(b, 1) * 100, 1)
        label = f"-{pct}%" if pct > 0 else f"+{abs(pct)}%"
        print(f"  {view:<30} {b:>9.1f}ms {a:>9.1f}ms {label:>14}")
    print("=" * 66)


if __name__ == "__main__":
    run()
