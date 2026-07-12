"""
run_all_transforms.py — Master ETL transform pipeline.

Runs all dimension and fact table population scripts in dependency order:
  1. populate_dim_pages.py  — upsert page metadata
  2. populate_dates.py      — extend dim_dates if needed
  3. populate_fct_sessions.py — load GA4 sessions into fact layer
  4. populate_fct_events.py  — load clickstream events into fact layer

Prints progress for each step, total time, and final row counts.
"""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _row_count(table: str) -> int:
    from utils.db import query_df

    df = query_df(f"SELECT COUNT(*) AS n FROM {table}")
    return int(df["n"].iloc[0])


def _print_step(n: int, name: str) -> None:
    print(f"\n[{n}/4] {name}")
    print("      " + "-" * 48)


def run(verbose: bool = True) -> dict:
    """Run all transform steps. Returns timing and row count summary."""
    pipeline_start = time.perf_counter()
    results: dict[str, dict] = {}

    # ── Step 1: dim_pages ────────────────────────────────────────────────────
    if verbose:
        _print_step(1, "populate_dim_pages.py")
    t0 = time.perf_counter()
    from sql.populate_dim_pages import run as run_dim_pages

    n1 = run_dim_pages(verbose=verbose)
    results["dim_pages"] = {"rows_affected": n1, "elapsed_s": time.perf_counter() - t0}
    if verbose:
        print(f"      Elapsed: {results['dim_pages']['elapsed_s']:.2f}s")

    # ── Step 2: dim_dates — extend to cover current year ────────────────────
    if verbose:
        _print_step(2, "populate_dates.py (extend to current year)")
    t0 = time.perf_counter()
    from sql.populate_dates import populate as populate_dates

    current_year_end = date(date.today().year, 12, 31)
    n2 = populate_dates(start=date(2023, 1, 1), end=current_year_end)
    results["dim_dates"] = {"rows_affected": n2, "elapsed_s": time.perf_counter() - t0}
    if verbose:
        print(f"      Inserted {n2} new date rows (already-existing rows skipped).")
        print(f"      Elapsed: {results['dim_dates']['elapsed_s']:.2f}s")

    # ── Step 3: fct_sessions ─────────────────────────────────────────────────
    if verbose:
        _print_step(3, "populate_fct_sessions.py")
    t0 = time.perf_counter()
    from sql.populate_fct_sessions import run as run_fct_sessions

    n3 = run_fct_sessions(verbose=verbose)
    results["fct_sessions"] = {
        "rows_affected": n3,
        "elapsed_s": time.perf_counter() - t0,
    }
    if verbose:
        print(f"      Elapsed: {results['fct_sessions']['elapsed_s']:.2f}s")

    # ── Step 4: fct_events ───────────────────────────────────────────────────
    if verbose:
        _print_step(4, "populate_fct_events.py")
    t0 = time.perf_counter()
    from sql.populate_fct_events import run as run_fct_events

    n4 = run_fct_events(verbose=verbose)
    results["fct_events"] = {"rows_affected": n4, "elapsed_s": time.perf_counter() - t0}
    if verbose:
        print(f"      Elapsed: {results['fct_events']['elapsed_s']:.2f}s")

    total_elapsed = time.perf_counter() - pipeline_start

    # ── Final row counts ─────────────────────────────────────────────────────
    counts = {
        "dim_pages": _row_count("dim_pages"),
        "dim_dates": _row_count("dim_dates"),
        "fct_sessions": _row_count("fct_sessions"),
        "fct_events": _row_count("fct_events"),
    }

    if verbose:
        sep = "=" * 56
        print(f"\n{sep}")
        print("  ETL TRANSFORM PIPELINE COMPLETE")
        print(sep)
        print(f"  Total time:        {total_elapsed:.2f}s")
        print("\n  Final row counts:")
        for tbl, cnt in counts.items():
            print(f"    {tbl:<18} {cnt:>8,} rows")
        print(sep)

    return {
        "steps": results,
        "final_counts": counts,
        "total_elapsed": total_elapsed,
    }


if __name__ == "__main__":
    run(verbose=True)
