"""
Platform summary report generator.
Loads key metrics from all views and raw tables, prints a formatted report,
and saves to data/processed/platform_summary.txt.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.db import query_df

OUTPUT = ROOT / "data" / "processed" / "platform_summary.txt"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def _safe(df, col, default=0):
    try:
        v = df[col].iloc[0]
        return v if v is not None else default
    except Exception:
        return default


def collect_metrics() -> dict:
    metrics = {}

    # Total sessions and users
    df = query_df("""
        SELECT SUM(sessions) AS total_sessions,
               SUM(new_users) AS total_new_users,
               SUM(pageviews) AS total_pageviews,
               ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS avg_bounce_rate_pct,
               ROUND(AVG(session_duration_s), 1) AS avg_session_duration_s,
               SUM(conversions) AS total_conversions,
               SUM(revenue)     AS total_revenue
        FROM raw_ga4_sessions
    """)
    metrics["total_sessions"]        = int(_safe(df, "total_sessions", 0) or 0)
    metrics["total_new_users"]       = int(_safe(df, "total_new_users", 0) or 0)
    metrics["total_pageviews"]       = int(_safe(df, "total_pageviews", 0) or 0)
    metrics["avg_bounce_rate_pct"]   = float(_safe(df, "avg_bounce_rate_pct", 0) or 0)
    metrics["avg_session_duration_s"]= float(_safe(df, "avg_session_duration_s", 0) or 0)
    metrics["total_conversions"]     = int(_safe(df, "total_conversions", 0) or 0)
    metrics["total_revenue"]         = float(_safe(df, "total_revenue", 0) or 0)
    metrics["overall_cvr_pct"]       = round(
        metrics["total_conversions"] / metrics["total_sessions"] * 100, 4
    ) if metrics["total_sessions"] else 0.0

    # Server logs
    df2 = query_df("SELECT COUNT(*) n FROM raw_server_logs")
    metrics["total_server_log_rows"] = int(_safe(df2, "n", 0))

    # Clickstream
    df3 = query_df("SELECT COUNT(*) n FROM raw_clickstream_events")
    metrics["total_clickstream_events"] = int(_safe(df3, "n", 0))

    # SEO scrape
    df4 = query_df("""
        SELECT COUNT(*) AS total_pages,
               ROUND(AVG(load_time_ms), 0) AS avg_load_time_ms,
               COUNT(CASE WHEN meta_description IS NULL OR meta_description = '' THEN 1 END) AS missing_meta
        FROM raw_scrape_pages WHERE http_status = 200
    """)
    metrics["total_scraped_pages"]  = int(_safe(df4, "total_pages", 0))
    metrics["avg_load_time_ms"]     = float(_safe(df4, "avg_load_time_ms", 0) or 0)
    metrics["pages_missing_meta"]   = int(_safe(df4, "missing_meta", 0))

    # dim_dates
    df5 = query_df("SELECT COUNT(*) n FROM dim_dates")
    metrics["dim_dates_rows"] = int(_safe(df5, "n", 0))

    # Date range from GA4
    df6 = query_df("SELECT MIN(session_date) mn, MAX(session_date) mx FROM raw_ga4_sessions")
    metrics["ga4_date_min"] = str(_safe(df6, "mn", "N/A"))
    metrics["ga4_date_max"] = str(_safe(df6, "mx", "N/A"))

    # Top channel
    df7 = query_df("""
        SELECT channel_grouping, SUM(sessions) n FROM raw_ga4_sessions
        GROUP BY channel_grouping ORDER BY n DESC LIMIT 1
    """)
    metrics["top_channel"] = str(_safe(df7, "channel_grouping", "N/A"))
    metrics["top_channel_sessions"] = int(_safe(df7, "n", 0) or 0)

    return metrics


def format_report(m: dict) -> str:
    sep = "=" * 60
    lines = [
        sep,
        "  ANALYTICS INTELLIGENCE PLATFORM - SUMMARY REPORT",
        sep,
        "",
        "-- TRAFFIC --------------------------------------------------",
        f"  GA4 Date Range:        {m['ga4_date_min']} to {m['ga4_date_max']}",
        f"  Total Sessions:        {m['total_sessions']:>12,}",
        f"  Total New Users:       {m['total_new_users']:>12,}",
        f"  Total Pageviews:       {m['total_pageviews']:>12,}",
        f"  Avg Bounce Rate:       {m['avg_bounce_rate_pct']:>11.2f}%",
        f"  Avg Session Duration:  {m['avg_session_duration_s']:>11.1f}s",
        f"  Top Channel:           {m['top_channel']} ({m['top_channel_sessions']:,} sessions)",
        "",
        "-- CONVERSIONS -----------------------------------------------",
        f"  Total Goal Completions:{m['total_conversions']:>12,}",
        f"  Overall CVR:           {m['overall_cvr_pct']:>11.4f}%",
        f"  Total Revenue:         ${m['total_revenue']:>11,.2f}",
        "",
        "-- SEO -------------------------------------------------------",
        f"  Total Pages Scraped:   {m['total_scraped_pages']:>12,}",
        f"  Avg Page Load Time:    {m['avg_load_time_ms']:>11.0f}ms",
        f"  Pages Missing Meta:    {m['pages_missing_meta']:>12,}",
        "",
        "-- DATA LAYER ------------------------------------------------",
        f"  Server Log Rows:       {m['total_server_log_rows']:>12,}",
        f"  Clickstream Events:    {m['total_clickstream_events']:>12,}",
        f"  dim_dates Rows:        {m['dim_dates_rows']:>12,}",
        "",
        sep,
    ]
    return "\n".join(lines)


def main():
    print("Collecting metrics from PostgreSQL...")
    m = collect_metrics()
    report = format_report(m)
    print(report)
    OUTPUT.write_text(report, encoding="utf-8")
    print(f"\nReport saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
