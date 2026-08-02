"""Cache management utilities for the Analytics Intelligence Platform.

Provides helpers to clear, warm up, inspect, and log Streamlit cache
and query-level performance data.
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
_CACHE_LOG_FILE = _PROCESSED_DIR / "cache_performance.json"


def clear_all_caches() -> None:
    """Clear all Streamlit st.cache_data caches.

    Call from within a Streamlit page: any cached function results are
    discarded and will be recomputed on the next access.
    """
    try:
        import streamlit as st
        st.cache_data.clear()
        logger.info("All st.cache_data caches cleared at %s", datetime.now().isoformat())
    except Exception as exc:
        logger.warning("Could not clear Streamlit cache: %s", exc)


def get_cache_stats() -> dict:
    """Return a summary of cache usage from the performance log.

    Reads the JSON log written by log_cache_performance() and computes
    hit rate, total calls, and average query execution time.

    Returns:
        Dict with keys: total_calls, cache_hits, cache_misses, hit_rate_pct,
        avg_query_ms, log_file_exists.
    """
    if not _CACHE_LOG_FILE.exists():
        return {
            "total_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "hit_rate_pct": 0.0,
            "avg_query_ms": 0.0,
            "log_file_exists": False,
        }

    try:
        with open(_CACHE_LOG_FILE, encoding="utf-8") as f:
            entries = json.load(f)
    except Exception:
        return {"total_calls": 0, "cache_hits": 0, "cache_misses": 0,
                "hit_rate_pct": 0.0, "avg_query_ms": 0.0, "log_file_exists": True}

    total = len(entries)
    hits = sum(1 for e in entries if e.get("from_cache", False))
    misses = total - hits
    avg_ms = (
        sum(e.get("duration_ms", 0) for e in entries if not e.get("from_cache", False))
        / max(misses, 1)
    )
    return {
        "total_calls": total,
        "cache_hits": hits,
        "cache_misses": misses,
        "hit_rate_pct": round(hits / max(total, 1) * 100, 1),
        "avg_query_ms": round(avg_ms, 1),
        "log_file_exists": True,
    }


def warm_up_cache() -> dict:
    """Pre-load the most common DB queries to warm the query-result cache.

    Executes a set of lightweight diagnostic queries so that the first
    real page load is faster. Returns a status dict.

    Returns:
        Dict with keys: warmed (int count), errors (list of str).
    """
    from utils.db import query_df

    warm_queries = [
        ("ga4_count", "SELECT COUNT(*) AS n FROM raw_ga4_sessions"),
        ("clickstream_count", "SELECT COUNT(*) AS n FROM raw_clickstream_events"),
        ("scrape_count", "SELECT COUNT(*) AS n FROM raw_scrape_pages"),
        ("vw_traffic_sample", "SELECT * FROM vw_traffic LIMIT 1"),
        ("vw_conversions_sample", "SELECT * FROM vw_conversions LIMIT 1"),
        ("vw_seo_sample", "SELECT * FROM vw_seo LIMIT 1"),
    ]

    warmed = 0
    errors: list[str] = []
    for name, sql in warm_queries:
        try:
            query_df(sql)
            warmed += 1
            logger.debug("Cache warm-up: %s OK", name)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            logger.warning("Cache warm-up failed for %s: %s", name, exc)

    logger.info("Cache warm-up complete: %d/%d queries succeeded", warmed, len(warm_queries))
    return {"warmed": warmed, "total": len(warm_queries), "errors": errors}


def cache_key_generator(query: str, params: dict | None = None) -> str:
    """Generate a deterministic cache key for a SQL query + params pair.

    Uses SHA-256 of the normalised SQL (whitespace collapsed) and sorted
    params JSON so that logically identical queries share the same key.

    Args:
        query:  SQL string (may contain :name placeholders).
        params: Optional parameter dict.

    Returns:
        Hex string cache key (64 characters).
    """
    normalised = " ".join(query.split())
    params_str = json.dumps(params or {}, sort_keys=True)
    raw = f"{normalised}||{params_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def log_cache_performance(
    query: str,
    duration_ms: float,
    from_cache: bool = False,
    params: dict | None = None,
) -> None:
    """Append a query execution record to the performance log.

    Creates data/processed/ if it does not exist. The log is a JSON array
    of records; it is rotated (capped at 1 000 entries) to prevent unbounded
    growth.

    Args:
        query:       The SQL that was executed.
        duration_ms: Wall-clock execution time in milliseconds.
        from_cache:  True if the result came from Streamlit cache.
        params:      Bound parameters (stored for debugging).
    """
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "cache_key": cache_key_generator(query, params),
        "query_preview": query[:120].replace("\n", " "),
        "duration_ms": round(duration_ms, 2),
        "from_cache": from_cache,
    }

    existing: list[dict] = []
    if _CACHE_LOG_FILE.exists():
        try:
            with open(_CACHE_LOG_FILE, encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    existing.append(entry)
    # Keep last 1 000 entries
    if len(existing) > 1000:
        existing = existing[-1000:]

    try:
        with open(_CACHE_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except Exception as exc:
        logger.warning("Could not write cache performance log: %s", exc)
