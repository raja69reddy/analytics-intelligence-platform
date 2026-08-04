"""Day 54 — Run EXPLAIN ANALYZE on all SQL views and save execution times.

Measures each view's execution time over 3 runs (average), extracts
the PostgreSQL Execution Time from EXPLAIN ANALYZE, and saves results
to data/processed/query_times.csv.
"""

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_engine, query_df
from sqlalchemy import text

OUT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "query_times.csv"
)

VIEWS = [
    "vw_traffic",
    "vw_daily_traffic",
    "vw_channel_performance",
    "vw_top_pages",
    "vw_behavior",
    "vw_conversions",
    "vw_seo",
    "vw_funnel",
]


def _explain_exec_ms(view: str) -> float:
    """Return PostgreSQL's own Execution Time (ms) from EXPLAIN ANALYZE."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(f"EXPLAIN ANALYZE SELECT * FROM {view}"))
        lines = [r[0] for r in result]
    for line in lines:
        if "Execution Time" in line:
            # "Execution Time: 12.345 ms"
            try:
                return float(line.split(":")[1].strip().split()[0])
            except Exception:
                pass
    return -1.0


def _wall_ms(view: str, runs: int = 3) -> float:
    """Measure wall-clock time (ms) to SELECT * from a view, averaged over runs."""
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        query_df(f"SELECT * FROM {view}")
        times.append((time.perf_counter() - t0) * 1000)
    return round(sum(times) / len(times), 1)


def run() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    print("=" * 64)
    print("  Day 54 — EXPLAIN ANALYZE on All SQL Views")
    print("=" * 64)
    print(f"  {'View':<30} {'Wall ms':>10}  {'PG Exec ms':>12}  {'Status'}")
    print("  " + "-" * 58)

    for view in VIEWS:
        try:
            wall = _wall_ms(view)
            pg_exec = _explain_exec_ms(view)
            tag = "SLOW" if wall > 500 else ("MED" if wall > 100 else "fast")
            print(f"  {view:<30} {wall:>9.1f}  {pg_exec:>11.3f}  [{tag}]")
            rows.append({
                "view": view,
                "wall_ms_avg": wall,
                "pg_exec_ms": pg_exec,
                "tag": tag,
                "measured_at": datetime.now().isoformat(),
            })
        except Exception as exc:
            print(f"  {view:<30} ERROR: {exc}")
            rows.append({
                "view": view,
                "wall_ms_avg": -1,
                "pg_exec_ms": -1,
                "tag": "ERROR",
                "measured_at": datetime.now().isoformat(),
            })

    # Save to CSV
    fieldnames = ["view", "wall_ms_avg", "pg_exec_ms", "tag", "measured_at"]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("  " + "-" * 58)
    top3 = sorted(rows, key=lambda r: -r["wall_ms_avg"])[:3]
    print(f"\n  Top 3 slowest views:")
    for i, r in enumerate(top3, 1):
        print(f"    #{i} {r['view']}: {r['wall_ms_avg']} ms (wall) / {r['pg_exec_ms']} ms (PG)")

    print(f"\n  Results saved to: {OUT_PATH}")
    print("=" * 64)


if __name__ == "__main__":
    run()
