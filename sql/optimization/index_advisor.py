"""Index advisor for the web_analytics PostgreSQL database.

Public API:
  analyze_missing_indexes(table)  — suggest indexes for a table based on query patterns
  analyze_unused_indexes(table)   — find indexes with zero or low usage
  get_index_usage_stats()         — pull pg_stat_user_indexes for all tables
  recommend_indexes()             — return prioritised list of recommendations
  apply_recommended_indexes()     — create the top 3 recommended indexes in PostgreSQL
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from utils.db import get_engine, query_df
from sqlalchemy import text

# ── Table registry — columns frequently used in WHERE / JOIN / GROUP BY ──────

# Maps each raw/fact/dim table to its high-value filter columns.
# These drive missing-index analysis without requiring a query log.
_TABLE_FILTER_COLS: dict[str, list[str]] = {
    "raw_ga4_sessions": [
        "session_date",
        "channel_grouping",
        "source",
        "device_category",
        "landing_page",
    ],
    "raw_server_logs": [
        "log_time",
        "status_code",
        "url",
        "ip_address",
    ],
    "raw_clickstream_events": [
        "event_name",
        "event_time",
        "page_url",
        "session_id",
    ],
    "raw_scrape_pages": [
        "url",
        "http_status",
        "scraped_at",
        "word_count",
    ],
    "fct_sessions": [
        "date_id",
        "channel_grouping",
        "device_category",
    ],
    "fct_events": [
        "date_id",
        "event_name",
        "session_id",
    ],
    "dim_dates": [
        "full_date",
        "year",
        "month",
    ],
}

# Minimum scans before we consider an index "used"
_MIN_SCANS_THRESHOLD = 5


# ── Helpers ───────────────────────────────────────────────────────────────────

def _existing_indexes(table: str) -> list[dict]:
    """Return all indexes that exist on *table* from pg_indexes."""
    df = query_df(
        "SELECT indexname, indexdef "
        "FROM pg_indexes "
        "WHERE tablename = :t",
        params={"t": table},
    )
    return df.to_dict("records")


def _table_exists(table: str) -> bool:
    df = query_df(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t",
        params={"t": table},
    )
    return len(df) > 0


def _column_exists(table: str, col: str) -> bool:
    df = query_df(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c",
        params={"t": table, "c": col},
    )
    return len(df) > 0


# ── Public API ────────────────────────────────────────────────────────────────

def get_index_usage_stats() -> list[dict]:
    """Pull live index usage statistics from pg_stat_user_indexes.

    Returns:
        List of dicts with keys:
          tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
    """
    df = query_df(
        "SELECT relname AS tablename, indexrelname AS indexname, "
        "       idx_scan, idx_tup_read, idx_tup_fetch "
        "FROM pg_stat_user_indexes "
        "ORDER BY relname, idx_scan DESC"
    )
    return df.to_dict("records")


def analyze_missing_indexes(table: str) -> list[dict]:
    """Suggest indexes for *table* based on known filter-column patterns.

    Checks which high-value columns lack a covering index and returns
    one recommendation per gap.

    Returns:
        List of dicts: { table, column, reason, priority, ddl }
    """
    if not _table_exists(table):
        return []

    existing = _existing_indexes(table)
    existing_defs = " ".join(idx["indexdef"].lower() for idx in existing)

    filter_cols = _TABLE_FILTER_COLS.get(table, [])
    recommendations = []

    for col in filter_cols:
        if not _column_exists(table, col):
            continue
        # Check if the column already has a single-column or leading composite index
        col_covered = (
            f"({col})" in existing_defs
            or f"({col}," in existing_defs
            or f"on {table} ({col}" in existing_defs
            or f"on {table} using btree ({col}" in existing_defs
        )
        if not col_covered:
            idx_name = f"idx_{table[:12]}_{col[:16]}"
            recommendations.append(
                {
                    "table": table,
                    "column": col,
                    "reason": f"Column '{col}' used in WHERE/JOIN/GROUP BY but has no index",
                    "priority": "HIGH" if col.endswith(("_date", "_time", "_id", "_code")) else "MEDIUM",
                    "ddl": f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({col})",
                }
            )

    return recommendations


def analyze_unused_indexes(table: str) -> list[dict]:
    """Find indexes on *table* that have never been scanned (idx_scan = 0).

    Returns:
        List of dicts: { tablename, indexname, idx_scan, recommendation }
    """
    df = query_df(
        "SELECT relname AS tablename, indexrelname AS indexname, idx_scan "
        "FROM pg_stat_user_indexes "
        "WHERE relname = :t AND idx_scan < :threshold "
        "ORDER BY idx_scan",
        params={"t": table, "threshold": _MIN_SCANS_THRESHOLD},
    )
    results = df.to_dict("records")
    for r in results:
        r["recommendation"] = (
            "Consider dropping this index — it has never (or rarely) been used "
            "and adds write overhead"
            if r["idx_scan"] == 0
            else f"Low-usage index (only {r['idx_scan']} scans) — monitor before dropping"
        )
    return results


def recommend_indexes() -> list[dict]:
    """Return a prioritised list of index recommendations across all tracked tables.

    Combines missing-index analysis with usage stats to rank suggestions.

    Returns:
        List of recommendation dicts sorted by priority (HIGH first), deduplicated.
    """
    all_recs: list[dict] = []
    usage = {r["indexname"]: r["idx_scan"] for r in get_index_usage_stats()}

    for table in _TABLE_FILTER_COLS:
        recs = analyze_missing_indexes(table)
        for r in recs:
            idx_name = r["ddl"].split("EXISTS")[1].split("ON")[0].strip()
            existing_scans = usage.get(idx_name, None)
            if existing_scans is not None:
                r["note"] = f"Index exists but has only {existing_scans} scans"
            all_recs.append(r)

    # Sort: HIGH priority first, then MEDIUM
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_recs.sort(key=lambda r: priority_order.get(r.get("priority", "LOW"), 2))

    # Deduplicate by DDL
    seen_ddl: set[str] = set()
    unique: list[dict] = []
    for r in all_recs:
        if r["ddl"] not in seen_ddl:
            seen_ddl.add(r["ddl"])
            unique.append(r)

    return unique


def apply_recommended_indexes(limit: int = 3) -> list[dict]:
    """Create the top *limit* recommended indexes in PostgreSQL.

    Only creates indexes that do not already exist (IF NOT EXISTS).

    Returns:
        List of dicts: { ddl, status, elapsed_ms }
    """
    import time

    recs = recommend_indexes()[:limit]
    engine = get_engine()
    results = []

    for r in recs:
        t0 = time.perf_counter()
        try:
            with engine.begin() as conn:
                conn.execute(text(r["ddl"]))
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(
                {
                    "ddl": r["ddl"],
                    "table": r["table"],
                    "column": r["column"],
                    "priority": r["priority"],
                    "status": "created",
                    "elapsed_ms": round(elapsed, 1),
                }
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(
                {
                    "ddl": r["ddl"],
                    "table": r["table"],
                    "column": r["column"],
                    "priority": r["priority"],
                    "status": f"error: {exc}",
                    "elapsed_ms": round(elapsed, 1),
                }
            )

    return results
