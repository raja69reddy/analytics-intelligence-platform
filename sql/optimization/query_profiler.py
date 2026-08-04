"""Query profiling tools using EXPLAIN ANALYZE.

Public API:
  profile_query(sql)             — run EXPLAIN ANALYZE, return plan text + timing
  get_execution_plan(sql)        — return structured JSON plan from PostgreSQL
  identify_bottlenecks(plan)     — list slow/expensive nodes in the plan
  suggest_optimizations(plan)    — return actionable suggestions
  benchmark_query(sql, runs=5)   — wall-clock average over N runs
  save_profile_results(results)  — persist to data/processed/query_profiles.csv
"""

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from utils.db import get_engine, query_df
from sqlalchemy import text

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
PROFILES_CSV = OUT_DIR / "query_profiles.csv"

# Node types that signal potential performance issues
_SLOW_NODE_TYPES = {
    "Seq Scan": "sequential scan (no index used)",
    "Sort": "in-memory or on-disk sort",
    "Hash": "hash build (memory pressure risk)",
    "Materialize": "materialised subplan (repeated evaluation)",
    "Gather": "parallel worker overhead",
    "Nested Loop": "nested-loop join (can be O(n²) on large sets)",
}

_HIGH_COST_THRESHOLD = 1000.0  # estimated cost units above which a node is flagged
_SLOW_MS_THRESHOLD = 100.0     # actual time (ms) above which a node is flagged


# ── Core helpers ─────────────────────────────────────────────────────────────

def profile_query(sql: str) -> dict:
    """Run EXPLAIN ANALYZE and return plan text, pg execution time, and row count.

    Returns:
        {
          "plan_text": list[str],     # raw EXPLAIN ANALYZE output lines
          "pg_exec_ms": float,        # PostgreSQL Execution Time
          "pg_plan_ms": float,        # PostgreSQL Planning Time
          "rows_returned": int,       # actual rows from the SELECT
          "sql_preview": str,
        }
    """
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(f"EXPLAIN ANALYZE {sql}"))
        lines = [r[0] for r in rows]

    pg_exec_ms = -1.0
    pg_plan_ms = -1.0
    for line in lines:
        if "Execution Time" in line:
            try:
                pg_exec_ms = float(line.split(":")[1].strip().split()[0])
            except Exception:
                pass
        if "Planning Time" in line:
            try:
                pg_plan_ms = float(line.split(":")[1].strip().split()[0])
            except Exception:
                pass

    return {
        "plan_text": lines,
        "pg_exec_ms": pg_exec_ms,
        "pg_plan_ms": pg_plan_ms,
        "sql_preview": " ".join(sql.split())[:120],
    }


def get_execution_plan(sql: str) -> dict:
    """Return the structured JSON execution plan from PostgreSQL.

    Uses EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) for full detail.

    Returns:
        The first element of the JSON plan array (the root node dict).
    """
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}")
        )
        json_str = rows.fetchone()[0]

    plan_list = json.loads(json_str) if isinstance(json_str, str) else json_str
    return plan_list[0] if plan_list else {}


def _walk_nodes(node: dict, depth: int = 0) -> list[dict]:
    """Recursively collect all plan nodes into a flat list."""
    results = [{"depth": depth, **node}]
    for child in node.get("Plans", []):
        results.extend(_walk_nodes(child, depth + 1))
    return results


def identify_bottlenecks(plan: dict) -> list[dict]:
    """Find expensive or problematic nodes in a JSON execution plan.

    Args:
        plan: Root plan dict from get_execution_plan().

    Returns:
        List of dicts describing each bottleneck:
        { node_type, actual_ms, total_cost, rows, issue, depth }
    """
    root_node = plan.get("Plan", plan)
    nodes = _walk_nodes(root_node)
    bottlenecks = []

    for node in nodes:
        node_type = node.get("Node Type", "Unknown")
        actual_ms = node.get("Actual Total Time", 0.0)
        total_cost = node.get("Total Cost", 0.0)
        actual_rows = node.get("Actual Rows", 0)
        plan_rows = node.get("Plan Rows", 0)
        depth = node.get("depth", 0)

        issues = []

        if node_type in _SLOW_NODE_TYPES and actual_ms > _SLOW_MS_THRESHOLD:
            issues.append(_SLOW_NODE_TYPES[node_type])

        if total_cost > _HIGH_COST_THRESHOLD:
            issues.append(f"high estimated cost ({total_cost:.0f} units)")

        if plan_rows > 0 and actual_rows > plan_rows * 10:
            issues.append(
                f"row estimate off by {actual_rows / plan_rows:.1f}x "
                f"(planned {plan_rows}, got {actual_rows}) — stale stats?"
            )

        if node_type == "Seq Scan" and actual_rows > 1000:
            issues.append(f"full table scan on {actual_rows:,} rows — index candidate")

        if issues:
            bottlenecks.append(
                {
                    "node_type": node_type,
                    "actual_ms": actual_ms,
                    "total_cost": total_cost,
                    "actual_rows": actual_rows,
                    "depth": depth,
                    "issues": "; ".join(issues),
                }
            )

    bottlenecks.sort(key=lambda b: -b["actual_ms"])
    return bottlenecks


def suggest_optimizations(plan: dict) -> list[str]:
    """Return a list of human-readable optimization suggestions for the plan.

    Args:
        plan: Root plan dict from get_execution_plan().

    Returns:
        List of suggestion strings, most impactful first.
    """
    bottlenecks = identify_bottlenecks(plan)
    suggestions = []
    seen: set[str] = set()

    for b in bottlenecks:
        nt = b["node_type"]

        if nt == "Seq Scan" and b["actual_rows"] > 500:
            table_hint = b.get("Relation Name", "the table")
            s = f"Add an index on '{table_hint}' to eliminate Seq Scan ({b['actual_rows']:,} rows scanned)"
            if s not in seen:
                suggestions.append(s)
                seen.add(s)

        if nt == "Sort" and b["actual_ms"] > 50:
            s = "Consider an index that matches the ORDER BY / GROUP BY columns to avoid sort"
            if s not in seen:
                suggestions.append(s)
                seen.add(s)

        if nt == "Hash" and b["actual_ms"] > 100:
            s = "Large hash build detected — check work_mem setting (SET work_mem = '64MB')"
            if s not in seen:
                suggestions.append(s)
                seen.add(s)

        if nt == "Nested Loop" and b["actual_ms"] > 200:
            s = "Nested Loop on large sets — ensure join columns are indexed on the inner side"
            if s not in seen:
                suggestions.append(s)
                seen.add(s)

        if "stale stats" in b["issues"]:
            s = "Run ANALYZE on involved tables — row estimates are far off, causing bad plans"
            if s not in seen:
                suggestions.append(s)
                seen.add(s)

        if "high estimated cost" in b["issues"] and nt == "Seq Scan":
            s = "High-cost Seq Scan: consider a partial index if only a subset of rows is queried"
            if s not in seen:
                suggestions.append(s)
                seen.add(s)

    if not suggestions:
        suggestions.append("No major bottlenecks detected — query plan looks healthy")

    return suggestions


def benchmark_query(sql: str, runs: int = 5) -> dict:
    """Measure wall-clock execution time averaged over N runs.

    Args:
        sql:  SELECT statement to benchmark.
        runs: Number of timed repetitions.

    Returns:
        { avg_ms, min_ms, max_ms, runs, sql_preview }
    """
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        query_df(sql)
        times.append((time.perf_counter() - t0) * 1000)

    return {
        "avg_ms": round(sum(times) / len(times), 2),
        "min_ms": round(min(times), 2),
        "max_ms": round(max(times), 2),
        "runs": runs,
        "sql_preview": " ".join(sql.split())[:120],
    }


def save_profile_results(results: list[dict], path: Path | None = None) -> Path:
    """Append profiling results to a CSV file.

    Args:
        results: List of dicts (each from benchmark_query() or profile_query()).
        path:    Destination file; defaults to data/processed/query_profiles.csv.

    Returns:
        The Path written to.
    """
    out = path or PROFILES_CSV
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "profiled_at", "label", "sql_preview",
        "avg_ms", "min_ms", "max_ms", "pg_exec_ms", "pg_plan_ms", "runs",
    ]
    write_header = not out.exists()
    with open(out, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        ts = datetime.now().isoformat()
        for r in results:
            writer.writerow({"profiled_at": ts, **r})

    return out


def print_profile(label: str, sql: str, runs: int = 3) -> dict:
    """Profile + benchmark a query and print a formatted report.

    Args:
        label: Human-readable name for the query.
        sql:   SELECT statement.
        runs:  Benchmark repetitions.

    Returns:
        Combined result dict suitable for save_profile_results().
    """
    bench = benchmark_query(sql, runs=runs)
    prof = profile_query(sql)
    try:
        plan = get_execution_plan(sql)
        bottlenecks = identify_bottlenecks(plan)
        suggestions = suggest_optimizations(plan)
    except Exception:
        bottlenecks = []
        suggestions = ["Could not retrieve JSON plan"]

    print(f"\n  [{label}]")
    print(f"    Wall-clock avg : {bench['avg_ms']:.1f} ms  (min {bench['min_ms']:.1f} / max {bench['max_ms']:.1f})")
    print(f"    PG exec time   : {prof['pg_exec_ms']:.3f} ms")
    print(f"    PG plan time   : {prof['pg_plan_ms']:.3f} ms")
    if bottlenecks:
        print(f"    Bottlenecks    : {len(bottlenecks)}")
        for b in bottlenecks[:2]:
            print(f"      - {b['node_type']} ({b['actual_ms']:.1f}ms): {b['issues'][:80]}")
    if suggestions and suggestions[0] != "No major bottlenecks detected — query plan looks healthy":
        print(f"    Suggestions:")
        for s in suggestions[:2]:
            print(f"      * {s[:90]}")

    return {
        "label": label,
        **bench,
        "pg_exec_ms": prof["pg_exec_ms"],
        "pg_plan_ms": prof["pg_plan_ms"],
    }
