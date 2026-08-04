"""Day 55 — Run full database maintenance (VACUUM ANALYZE all tables).

Captures bloat percentages and dead tuple counts before and after,
prints a maintenance report, and logs the run to pipeline_monitor.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sql.optimization.vacuum_analyzer import (
    TRACKED_TABLES,
    get_table_bloat,
    get_dead_tuples,
    run_full_maintenance,
    print_maintenance_report,
)

LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "pipeline_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_to_pipeline_monitor(results: list[dict], before: list[dict], after: list[dict]) -> Path:
    """Write a JSON maintenance log entry to pipeline_logs/."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"maintenance_{ts}.json"
    payload = {
        "run_at": datetime.now().isoformat(),
        "tables_vacuumed": len(results),
        "ok_count": sum(1 for r in results if r["status"] == "ok"),
        "error_count": sum(1 for r in results if r["status"] != "ok"),
        "total_elapsed_ms": round(sum(r["elapsed_ms"] for r in results), 1),
        "vacuum_results": results,
        "bloat_before": before,
        "bloat_after": after,
    }
    log_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return log_path


def run() -> None:
    print("=" * 72)
    print("  Day 55 - Full Database Maintenance")
    print("=" * 72)

    # ── Snapshot BEFORE ───────────────────────────────────────────────────────
    print("\n  Collecting pre-maintenance bloat stats...")
    before = [get_table_bloat(t) for t in TRACKED_TABLES]
    dead_before = [get_dead_tuples(t) for t in TRACKED_TABLES]

    print(f"\n  {'Table':<30} {'Bloat %':>10} {'Dead tuples':>14}")
    print("  " + "-" * 56)
    for b, d in zip(before, dead_before):
        print(f"  {b['table']:<30} {b['bloat_pct']:>9.2f}% {d['dead_tuples']:>13,}")

    # ── Run VACUUM ANALYZE ────────────────────────────────────────────────────
    print(f"\n  Running VACUUM ANALYZE on {len(TRACKED_TABLES)} tables...")
    results = run_full_maintenance()
    for r in results:
        tag = "OK " if r["status"] == "ok" else "ERR"
        print(f"    [{tag}] {r['table']:<30}  {r['elapsed_ms']:.0f} ms")

    # ── Snapshot AFTER ────────────────────────────────────────────────────────
    print("\n  Collecting post-maintenance bloat stats...")
    after = [get_table_bloat(t) for t in TRACKED_TABLES]
    dead_after = [get_dead_tuples(t) for t in TRACKED_TABLES]

    # ── Print maintenance report ──────────────────────────────────────────────
    print_maintenance_report(before=before, after=after)

    # ── Dead tuple summary ────────────────────────────────────────────────────
    print("  Dead Tuple Counts:")
    print(f"  {'Table':<30} {'Before':>10} {'After':>10}")
    print("  " + "-" * 52)
    dead_before_map = {d["table"]: d["dead_tuples"] for d in dead_before}
    for d in dead_after:
        before_count = dead_before_map.get(d["table"], 0)
        print(f"  {d['table']:<30} {before_count:>10,} {d['dead_tuples']:>10,}")

    # ── Log to pipeline monitor ───────────────────────────────────────────────
    log_path = _log_to_pipeline_monitor(results, before, after)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    total_ms = sum(r["elapsed_ms"] for r in results)

    print(f"\n  Maintenance complete: {ok_count}/{len(results)} tables OK  |  total {total_ms:.0f} ms")
    print(f"  Log saved to: {log_path}")


if __name__ == "__main__":
    run()
