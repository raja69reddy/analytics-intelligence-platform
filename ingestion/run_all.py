"""
Orchestration script: runs all 4 ingestion pipelines in order.

Usage:
    python ingestion/run_all.py --mode full
    python ingestion/run_all.py --mode incremental --since 2024-06-01
    python ingestion/run_all.py --mode full --pipeline ga4
    python ingestion/run_all.py --mode full --dry-run
"""
import argparse
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "data" / "processed" / "pipeline_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s run_all: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_all")

# ANSI color helpers (degrade gracefully on non-TTY)
_USE_COLOR = sys.stdout.isatty()


def _green(s: str) -> str:
    return f"\033[32m{s}\033[0m" if _USE_COLOR else s


def _red(s: str) -> str:
    return f"\033[31m{s}\033[0m" if _USE_COLOR else s


def _yellow(s: str) -> str:
    return f"\033[33m{s}\033[0m" if _USE_COLOR else s


def _row_count(table: str) -> int:
    from utils.db import query_df
    return int(query_df(f"SELECT COUNT(*) AS n FROM {table}")["n"].iloc[0])


def _run_pipeline(
    name: str,
    fn,
    mode: str,
    since: date | None,
    dry_run: bool,
) -> tuple[int | None, float, str]:
    """Run one ingestion function. Returns (rows, elapsed, status)."""
    logger.info(f"--- Starting {name} (mode={mode}, dry_run={dry_run}) ---")
    t0 = time.perf_counter()
    try:
        if dry_run:
            # Validate: just import and check the CSV source exists
            from pathlib import Path as P
            csv_map = {
                "ga4":         "ga4_sessions.csv",
                "server_logs": "server_logs.csv",
                "clickstream": "clickstream_events.csv",
                "scraper":     "scrape_pages.csv",
            }
            csv_path = ROOT / "data" / "raw" / csv_map.get(name, "")
            if not csv_path.exists():
                raise FileNotFoundError(f"CSV not found: {csv_path}")
            logger.info(f"DRY RUN — {name} validated (CSV exists, no insert)")
            rows = 0
        elif since is not None:
            rows = fn(mode=mode, since=since)
        else:
            rows = fn(mode=mode)
        elapsed = time.perf_counter() - t0
        status = "success"
        logger.info(f"--- {name} done: {rows} rows in {elapsed:.1f}s ---")
        return rows, elapsed, status
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        logger.error(f"{name} FAILED: {exc}")
        return None, elapsed, f"error: {exc}"


def _save_run_log(results: list, mode: str, dry_run: bool) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"run_{ts}.log"
    lines = [
        f"run_all.py — {datetime.now().isoformat()}",
        f"mode={mode}  dry_run={dry_run}",
        "-" * 60,
    ]
    for name, table, rows, elapsed, db_count, status in results:
        lines.append(
            f"{status:<10} {name:<14} rows={rows}  time={elapsed:.1f}s  table_total={db_count}"
        )
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all ingestion pipelines")
    parser.add_argument("--mode", choices=["full", "incremental"], required=True)
    parser.add_argument("--since", type=date.fromisoformat, default=None,
                        help="Start date for incremental mode (YYYY-MM-DD)")
    parser.add_argument("--pipeline", choices=["ga4", "server_logs", "clickstream", "scraper"],
                        default=None, help="Run only this pipeline (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate inputs without inserting any rows")
    args = parser.parse_args()

    if args.mode == "incremental" and args.since is None:
        parser.error("--since YYYY-MM-DD is required with --mode incremental")

    from ingestion.ga4 import ingest as ga4_ingest
    from ingestion.server_logs import ingest as server_ingest
    from ingestion.clickstream import ingest as clickstream_ingest
    from ingestion.scraper import ingest as scraper_ingest

    all_pipelines = [
        ("ga4",         ga4_ingest,         "raw_ga4_sessions"),
        ("server_logs", server_ingest,       "raw_server_logs"),
        ("clickstream", clickstream_ingest,  "raw_clickstream_events"),
        ("scraper",     scraper_ingest,      "raw_scrape_pages"),
    ]

    # Filter to requested pipeline if --pipeline supplied
    pipelines = (
        [p for p in all_pipelines if p[0] == args.pipeline]
        if args.pipeline else all_pipelines
    )

    if args.dry_run:
        print(_yellow(f"\n  DRY RUN — no data will be inserted\n"))

    wall_start = time.perf_counter()
    results = []

    # Progress indicator — simple counter since tqdm may not be installed
    total = len(pipelines)
    for idx, (name, fn, table) in enumerate(pipelines, start=1):
        print(f"  [{idx}/{total}] Running {name}...", flush=True)
        rows, elapsed, status = _run_pipeline(name, fn, args.mode, args.since, args.dry_run)
        db_count = _row_count(table) if not args.dry_run else None
        results.append((name, table, rows, elapsed, db_count, status))

    total_elapsed = time.perf_counter() - wall_start

    # Summary table
    print("\n" + "=" * 65)
    label = "DRY RUN" if args.dry_run else f"--mode {args.mode}"
    print(f"  run_all.py summary  {label}")
    print("=" * 65)
    for name, table, rows, elapsed, db_count, status in results:
        ok = status == "success"
        tag = _green("[OK]") if ok else _red("[ERR]")
        rows_str = str(rows) if rows is not None else "—"
        db_str   = str(db_count) if db_count is not None else "—"
        print(f"  {tag} {name:<14} {rows_str:>5} rows  {elapsed:>6.1f}s  |  {table}: {db_str} total")
    print("-" * 65)
    print(f"  Total wall time: {total_elapsed:.1f}s")
    print("=" * 65)

    # Save log
    log_path = _save_run_log(results, args.mode, args.dry_run)
    print(f"\n  Log saved to: {log_path}\n")


if __name__ == "__main__":
    main()
