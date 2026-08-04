"""VACUUM and table-maintenance helpers for the web_analytics database.

Public API:
  run_vacuum_analyze(table)     — VACUUM ANALYZE a single table
  get_table_bloat(table)        — estimate bloat % via pg_stat_user_tables
  get_dead_tuples(table)        — return dead tuple count and ratio
  run_full_maintenance()        — vacuum-analyze every tracked table
  print_maintenance_report()    — formatted console report
"""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from utils.db import get_engine, query_df
from sqlalchemy import text

TRACKED_TABLES = [
    "raw_ga4_sessions",
    "raw_server_logs",
    "raw_clickstream_events",
    "raw_scrape_pages",
    "fct_sessions",
    "fct_events",
    "dim_dates",
    "dim_pages",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pg_stat_row(table: str) -> dict:
    """Return a single row from pg_stat_user_tables for *table*."""
    df = query_df(
        "SELECT relname, n_live_tup, n_dead_tup, n_mod_since_analyze, "
        "       last_vacuum, last_autovacuum, last_analyze, last_autoanalyze, "
        "       seq_scan, idx_scan "
        "FROM pg_stat_user_tables "
        "WHERE relname = :t",
        params={"t": table},
    )
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def _table_size_bytes(table: str) -> int:
    """Return the on-disk size of *table* in bytes via pg_total_relation_size."""
    df = query_df(
        "SELECT pg_total_relation_size(:t) AS sz",
        params={"t": table},
    )
    return int(df["sz"].iloc[0]) if not df.empty else 0


# ── Public API ────────────────────────────────────────────────────────────────

def run_vacuum_analyze(table: str) -> dict:
    """Run VACUUM ANALYZE on a single table.

    PostgreSQL does not allow VACUUM inside a transaction, so we use
    AUTOCOMMIT mode via isolation_level=None.

    Returns:
        { table, elapsed_ms, status }
    """
    engine = get_engine()
    t0 = time.perf_counter()
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"VACUUM ANALYZE {table}"))
        elapsed = (time.perf_counter() - t0) * 1000
        return {"table": table, "elapsed_ms": round(elapsed, 1), "status": "ok"}
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        return {"table": table, "elapsed_ms": round(elapsed, 1), "status": f"error: {exc}"}


def get_dead_tuples(table: str) -> dict:
    """Return live/dead tuple counts and the dead-tuple ratio for *table*.

    Returns:
        { table, live_tuples, dead_tuples, dead_ratio_pct }
    """
    row = _pg_stat_row(table)
    if not row:
        return {"table": table, "live_tuples": 0, "dead_tuples": 0, "dead_ratio_pct": 0.0}

    live = int(row.get("n_live_tup", 0) or 0)
    dead = int(row.get("n_dead_tup", 0) or 0)
    total = live + dead
    ratio = round(dead / total * 100, 2) if total > 0 else 0.0

    return {
        "table": table,
        "live_tuples": live,
        "dead_tuples": dead,
        "dead_ratio_pct": ratio,
    }


def get_table_bloat(table: str) -> dict:
    """Estimate table bloat using pg_stat_user_tables and page-level stats.

    Bloat is approximated as:
        bloat_pct = (n_dead_tup / max(n_live_tup + n_dead_tup, 1)) * 100

    This is a lightweight estimate — for exact bloat use pgstattuple (extension).

    Returns:
        { table, size_bytes, size_kb, live_tuples, dead_tuples, bloat_pct, last_vacuum }
    """
    row = _pg_stat_row(table)
    size_bytes = _table_size_bytes(table)

    live = int(row.get("n_live_tup", 0) or 0) if row else 0
    dead = int(row.get("n_dead_tup", 0) or 0) if row else 0
    total = live + dead
    bloat_pct = round(dead / max(total, 1) * 100, 2)

    last_vacuum = row.get("last_vacuum") or row.get("last_autovacuum") if row else None
    last_vacuum_str = (
        last_vacuum.isoformat()[:19] if hasattr(last_vacuum, "isoformat") else str(last_vacuum)
    ) if last_vacuum else "never"

    return {
        "table": table,
        "size_bytes": size_bytes,
        "size_kb": round(size_bytes / 1024, 1),
        "live_tuples": live,
        "dead_tuples": dead,
        "bloat_pct": bloat_pct,
        "last_vacuum": last_vacuum_str,
    }


def run_full_maintenance() -> list[dict]:
    """Run VACUUM ANALYZE on every table in TRACKED_TABLES.

    Returns:
        List of result dicts from run_vacuum_analyze().
    """
    results = []
    for table in TRACKED_TABLES:
        result = run_vacuum_analyze(table)
        results.append(result)
    return results


def print_maintenance_report(
    before: list[dict] | None = None,
    after: list[dict] | None = None,
) -> None:
    """Print a formatted maintenance report.

    If *before* and *after* bloat snapshots are provided, shows before/after comparison.
    Otherwise fetches current bloat stats.
    """
    print("=" * 72)
    print(f"  DB Maintenance Report  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    if before and after:
        by_table_before = {r["table"]: r for r in before}
        print(f"\n  {'Table':<30} {'Before %':>10} {'After %':>10} {'Dead rows':>10} {'Size KB':>10}")
        print("  " + "-" * 70)
        for r in after:
            b = by_table_before.get(r["table"], {})
            b_pct = b.get("bloat_pct", 0.0)
            a_pct = r.get("bloat_pct", 0.0)
            dead = r.get("dead_tuples", 0)
            size_kb = r.get("size_kb", 0)
            tag = " <-- cleaned" if b_pct > 0 and a_pct < b_pct else ""
            print(f"  {r['table']:<30} {b_pct:>9.2f}% {a_pct:>9.2f}% {dead:>10,} {size_kb:>9.1f}{tag}")
    else:
        current = [get_table_bloat(t) for t in TRACKED_TABLES]
        print(f"\n  {'Table':<30} {'Bloat %':>10} {'Dead rows':>10} {'Live rows':>10} {'Size KB':>10}")
        print("  " + "-" * 70)
        for r in current:
            print(
                f"  {r['table']:<30} {r['bloat_pct']:>9.2f}% "
                f"{r['dead_tuples']:>10,} {r['live_tuples']:>10,} {r['size_kb']:>9.1f}"
            )
        print(f"\n  Last vacuum info:")
        for r in current:
            print(f"    {r['table']:<30}  last vacuum: {r['last_vacuum']}")

    print("\n" + "=" * 72)
