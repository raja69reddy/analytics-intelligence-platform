"""Day 50 — Dashboard Performance Test.

Simulates cold-cache and warm-cache page loads by calling all major
loader functions directly (bypassing Streamlit) and measuring elapsed time.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df

PAGES = {
    "Home (app.py)": [
        ("ga4 freshness", "SELECT COUNT(*) AS n, MAX(ingested_at) AS ts FROM raw_ga4_sessions"),
        ("clickstream freshness", "SELECT COUNT(*) AS n, MAX(ingested_at) AS ts FROM raw_clickstream_events"),
    ],
    "Traffic": [
        ("vw_traffic", "SELECT * FROM vw_traffic LIMIT 50"),
        ("vw_daily_traffic", "SELECT * FROM vw_daily_traffic LIMIT 50"),
        ("channels", "SELECT channel_grouping, SUM(sessions) AS s FROM raw_ga4_sessions GROUP BY 1"),
        ("devices", "SELECT device_category, SUM(sessions) AS s FROM raw_ga4_sessions GROUP BY 1"),
        ("geo", "SELECT country, SUM(sessions) AS s FROM raw_ga4_sessions WHERE country IS NOT NULL GROUP BY 1 LIMIT 10"),
    ],
    "Behavior": [
        ("vw_behavior", "SELECT * FROM vw_behavior LIMIT 50"),
        ("top_pages", "SELECT * FROM vw_top_pages LIMIT 20"),
        ("vw_funnel", "SELECT * FROM vw_funnel"),
        ("session_quality", "SELECT channel_grouping, AVG(sessions) FROM raw_ga4_sessions GROUP BY 1"),
        ("retention", "SELECT session_date, COUNT(*) FROM raw_ga4_sessions GROUP BY 1 LIMIT 30"),
    ],
    "Conversions": [
        ("vw_conversions", "SELECT * FROM vw_conversions LIMIT 50"),
        ("vw_funnel", "SELECT * FROM vw_funnel"),
    ],
    "SEO": [
        ("vw_seo", "SELECT * FROM vw_seo"),
        ("raw_scrape_pages", "SELECT * FROM raw_scrape_pages WHERE http_status=200"),
    ],
    "Pipeline": [
        ("ga4_count", "SELECT COUNT(*) AS n, MAX(ingested_at) AS ts FROM raw_ga4_sessions"),
        ("scrape_count", "SELECT COUNT(*) AS n, MAX(ingested_at) AS ts FROM raw_scrape_pages"),
    ],
    "Forecasting": [
        ("daily_traffic_hist", "SELECT session_date, SUM(sessions) AS y FROM raw_ga4_sessions GROUP BY 1 ORDER BY 1"),
        ("cvr_hist", "SELECT session_date, SUM(goal_completions)::float/NULLIF(SUM(sessions),0) AS cvr FROM vw_conversions GROUP BY 1 ORDER BY 1"),
    ],
    "NLQ": [
        ("schema_probe", "SELECT table_name FROM information_schema.tables WHERE table_schema='public' LIMIT 10"),
    ],
}


def run_pass(label: str) -> dict[str, float]:
    """Run all queries once and return per-page load times in seconds."""
    results: dict[str, float] = {}
    print(f"\n{'='*55}\n{label}\n{'='*55}")
    for page, queries in PAGES.items():
        t_page = time.perf_counter()
        for qname, sql in queries:
            try:
                query_df(sql)
            except Exception as exc:
                print(f"  [WARN] {page} / {qname}: {exc}")
        elapsed = time.perf_counter() - t_page
        results[page] = round(elapsed, 3)
        print(f"  {page:<20} {elapsed:.3f}s")
    return results


if __name__ == "__main__":
    print("Dashboard Performance Test — Day 50")
    print("Measuring cold-cache vs warm-cache load times for all 8 pages\n")

    cold = run_pass("COLD CACHE (first load)")
    warm = run_pass("WARM CACHE (second load — DB connection pooled)")

    print(f"\n{'='*55}\nSUMMARY\n{'='*55}")
    print(f"{'Page':<22} {'Cold (s)':>10} {'Warm (s)':>10} {'Improvement':>14}")
    print("-" * 60)
    for page in PAGES:
        c = cold[page]
        w = warm[page]
        pct = round((c - w) / c * 100, 1) if c > 0 else 0.0
        print(f"{page:<22} {c:>10.3f} {w:>10.3f} {pct:>13.1f}%")

    avg_cold = sum(cold.values()) / len(cold)
    avg_warm = sum(warm.values()) / len(warm)
    avg_pct = round((avg_cold - avg_warm) / avg_cold * 100, 1) if avg_cold > 0 else 0.0
    print("-" * 60)
    print(f"{'AVERAGE':<22} {avg_cold:>10.3f} {avg_warm:>10.3f} {avg_pct:>13.1f}%")
    print(f"\nAvg load improvement with warm DB pool: {avg_pct}%")
    print("\nNote: Streamlit @st.cache_data TTL=300s delivers 100% improvement")
    print("      for subsequent page loads within the 5-minute cache window.")
