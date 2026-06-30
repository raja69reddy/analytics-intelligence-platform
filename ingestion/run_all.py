"""
Orchestration script: runs all 4 ingestion pipelines in order.

Usage:
    python ingestion/run_all.py --mode full
    python ingestion/run_all.py --mode incremental --since 2024-06-01
"""
import argparse
import logging
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s run_all: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_all")


def _row_count(table: str) -> int:
    from utils.db import query_df
    return int(query_df(f"SELECT COUNT(*) AS n FROM {table}")["n"].iloc[0])


def _run_pipeline(name: str, fn, mode: str, since: date | None) -> tuple[int, float]:
    """Run one ingestion function, return (rows_inserted, elapsed_seconds)."""
    logger.info(f"--- Starting {name} ({mode}) ---")
    t0 = time.perf_counter()
    try:
        if since is not None:
            rows = fn(mode=mode, since=since)
        else:
            rows = fn(mode=mode)
    except Exception as exc:
        logger.error(f"{name} FAILED: {exc}")
        raise
    elapsed = time.perf_counter() - t0
    logger.info(f"--- {name} done: {rows} rows in {elapsed:.1f}s ---")
    return rows, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all ingestion pipelines")
    parser.add_argument("--mode", choices=["full", "incremental"], required=True)
    parser.add_argument("--since", type=date.fromisoformat, default=None,
                        help="Start date for incremental mode (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.mode == "incremental" and args.since is None:
        parser.error("--since YYYY-MM-DD is required with --mode incremental")

    # Import pipeline functions
    from ingestion.ga4 import ingest as ga4_ingest
    from ingestion.server_logs import ingest as server_ingest
    from ingestion.clickstream import ingest as clickstream_ingest
    from ingestion.scraper import ingest as scraper_ingest

    pipelines = [
        ("ga4",         ga4_ingest,         "raw_ga4_sessions"),
        ("server_logs", server_ingest,       "raw_server_logs"),
        ("clickstream", clickstream_ingest,  "raw_clickstream_events"),
        ("scraper",     scraper_ingest,      "raw_scrape_pages"),
    ]

    wall_start = time.perf_counter()
    results = []

    for name, fn, table in pipelines:
        rows, elapsed = _run_pipeline(name, fn, args.mode, args.since)
        db_count = _row_count(table)
        results.append((name, table, rows, elapsed, db_count))

    total_elapsed = time.perf_counter() - wall_start

    print("\n" + "=" * 60)
    print(f"  run_all.py summary  --mode {args.mode}")
    print("=" * 60)
    for name, table, rows, elapsed, db_count in results:
        status = "OK" if rows is not None else "ERROR"
        print(f"  [{status}] {name:<14} {rows:>5} rows inserted  {elapsed:>6.1f}s  |  {table}: {db_count} total")
    print("-" * 60)
    print(f"  Total wall time: {total_elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
