"""Day 52 — Stress test with 100k rows: load, benchmark, verify.

Generates ~100k GA4 sessions and ~100k clickstream events, loads them into
PostgreSQL, then benchmarks all key dashboard queries to verify performance
at scale.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mock_data.gen_ga4 as gen_ga4
import mock_data.gen_clickstream as gen_click
from utils.db import query_df

BENCHMARK_QUERIES = {
    "vw_daily_traffic": "SELECT * FROM vw_daily_traffic ORDER BY session_date",
    "vw_top_pages": "SELECT * FROM vw_top_pages",
    "vw_traffic": "SELECT * FROM vw_traffic LIMIT 500",
    "vw_seo": "SELECT * FROM vw_seo",
    "vw_funnel": "SELECT * FROM vw_funnel ORDER BY stage_order",
    "vw_conversions": "SELECT * FROM vw_conversions ORDER BY session_date",
    "channel agg (GA4)": (
        "SELECT channel_grouping, SUM(sessions) AS total_sessions, "
        "ROUND(AVG(session_duration_s)::numeric, 2) AS avg_dur "
        "FROM raw_ga4_sessions GROUP BY channel_grouping"
    ),
    "device split (GA4)": (
        "SELECT device_category, SUM(sessions) AS sessions "
        "FROM raw_ga4_sessions GROUP BY device_category"
    ),
    "event counts (clickstream)": (
        "SELECT event_name, COUNT(*) AS n "
        "FROM raw_clickstream_events GROUP BY event_name ORDER BY n DESC"
    ),
    "landing page ROI": (
        "SELECT landing_page, SUM(sessions) AS total_sessions, "
        "ROUND(SUM(revenue)::NUMERIC / NULLIF(SUM(sessions), 0), 4) AS rpv "
        "FROM raw_ga4_sessions WHERE landing_page IS NOT NULL AND sessions > 0 "
        "GROUP BY landing_page HAVING SUM(sessions) >= 5 ORDER BY rpv DESC"
    ),
    "content performance join": (
        "SELECT sp.url, sp.word_count, sp.load_time_ms, "
        "COALESCE(v.organic_sessions, 0) AS sessions "
        "FROM (SELECT DISTINCT ON (url) url, word_count, load_time_ms, "
        "meta_description, internal_links FROM raw_scrape_pages "
        "WHERE http_status = 200 ORDER BY url, scraped_at DESC) sp "
        "LEFT JOIN vw_seo v ON v.url = sp.url ORDER BY sessions DESC"
    ),
}

VERIFY_QUERIES = {
    "GA4 row count":       "SELECT COUNT(*) FROM raw_ga4_sessions",
    "Clickstream rows":    "SELECT COUNT(*) FROM raw_clickstream_events",
    "Distinct channels":   "SELECT COUNT(DISTINCT channel_grouping) FROM raw_ga4_sessions",
    "Distinct events":     "SELECT COUNT(DISTINCT event_name) FROM raw_clickstream_events",
    "GA4 date range":      "SELECT MIN(session_date), MAX(session_date) FROM raw_ga4_sessions",
    "vw_daily_traffic rows": "SELECT COUNT(*) FROM vw_daily_traffic",
    "vw_seo rows":         "SELECT COUNT(*) FROM vw_seo",
    "vw_funnel rows":      "SELECT COUNT(*) FROM vw_funnel",
}


def measure(sql: str, runs: int = 2) -> float:
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        query_df(sql)
        times.append((time.perf_counter() - t0) * 1000)
    return round(sum(times) / len(times), 1)


def run():
    print("=" * 65)
    print("Day 52 Stress Test — 100k row benchmark")
    print("=" * 65)

    # ── Step 1: Generate + load GA4 sessions ─────────────────────────
    print("\n[1/4] Generating ~100k GA4 sessions (days=90, sessions_per_day=1112)...")
    t0 = time.perf_counter()
    ga4_df = gen_ga4.generate(days=90, sessions_per_day=1112)
    elapsed = time.perf_counter() - t0
    print(f"      Generated {len(ga4_df):,} rows in {elapsed:.1f}s")

    print("      Loading into raw_ga4_sessions (TRUNCATE + insert)...")
    t0 = time.perf_counter()
    gen_ga4.load(ga4_df, mode="full")
    elapsed = time.perf_counter() - t0
    print(f"      Load complete in {elapsed:.1f}s")

    # ── Step 2: Generate + load clickstream events ────────────────────
    # ~140 sessions/day × 90 days × avg 8 events/session ≈ 100,800 events
    print("\n[2/4] Generating ~100k clickstream events (days=90, sessions_per_day=140)...")
    t0 = time.perf_counter()
    click_df = gen_click.generate(days=90, sessions_per_day=140)
    elapsed = time.perf_counter() - t0
    print(f"      Generated {len(click_df):,} rows in {elapsed:.1f}s")

    print("      Loading into raw_clickstream_events (TRUNCATE + insert)...")
    t0 = time.perf_counter()
    gen_click.load(click_df, mode="full")
    elapsed = time.perf_counter() - t0
    print(f"      Load complete in {elapsed:.1f}s")

    # ── Step 3: Verify data ───────────────────────────────────────────
    print("\n[3/4] Verifying data integrity...")
    all_ok = True
    for label, sql in VERIFY_QUERIES.items():
        df = query_df(sql)
        val = " | ".join(str(v) for v in df.iloc[0].values)
        print(f"      {label:<30} {val}")
        if "row count" in label.lower() or "rows" in label.lower():
            n = df.iloc[0, 0]
            if n == 0:
                print(f"  WARN: {label} returned 0 — something may be wrong")
                all_ok = False

    # ── Step 4: Benchmark queries ─────────────────────────────────────
    print("\n[4/4] Benchmarking dashboard queries (2-run average)...")
    print(f"\n  {'Query':<35} {'Avg ms':>10}  Status")
    print("  " + "-" * 58)

    timings: dict[str, float] = {}
    for name, sql in BENCHMARK_QUERIES.items():
        ms = measure(sql)
        timings[name] = ms
        tag = "SLOW" if ms > 2000 else ("MED" if ms > 500 else "OK  ")
        print(f"  {name:<35} {ms:>9.1f}  [{tag}]")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("STRESS TEST SUMMARY")
    print("=" * 65)
    print(f"  GA4 sessions loaded   : {len(ga4_df):>10,}")
    print(f"  Clickstream events    : {len(click_df):>10,}")
    total_rows = len(ga4_df) + len(click_df)
    print(f"  Total rows inserted   : {total_rows:>10,}")

    avg_ms = sum(timings.values()) / len(timings)
    slowest = max(timings, key=lambda k: timings[k])
    fastest = min(timings, key=lambda k: timings[k])
    slow_count = sum(1 for ms in timings.values() if ms > 2000)

    print(f"\n  Queries benchmarked   : {len(timings)}")
    print(f"  Average query time    : {avg_ms:.1f} ms")
    print(f"  Fastest query         : {fastest} ({timings[fastest]:.1f} ms)")
    print(f"  Slowest query         : {slowest} ({timings[slowest]:.1f} ms)")
    print(f"  Queries >2000 ms      : {slow_count}")

    status = "PASS" if all_ok and slow_count == 0 else ("WARN" if slow_count <= 2 else "FAIL")
    print(f"\n  Overall result        : {status}")
    print("=" * 65)

    if status == "PASS":
        print("\nAll charts verified: dashboard handles 100k rows with acceptable performance.")
    elif status == "WARN":
        print(f"\n{slow_count} query/queries exceeded 2000ms — consider adding indexes or caching.")
    else:
        print("\nSome queries are too slow for a 100k dataset. Review indexing strategy.")


if __name__ == "__main__":
    run()
