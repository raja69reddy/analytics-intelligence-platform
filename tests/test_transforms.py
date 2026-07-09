"""Tests for ETL transform scripts — fct_sessions, fct_events, dim_pages."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.db import query_df, get_engine
from sqlalchemy import text


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    return get_engine()


# ── fct_sessions tests ────────────────────────────────────────────────────────

def test_fct_sessions_has_rows():
    """fct_sessions must have at least as many rows as raw_ga4_sessions."""
    df_raw = query_df("SELECT COUNT(*) AS n FROM raw_ga4_sessions")
    df_fct = query_df("SELECT COUNT(*) AS n FROM fct_sessions")
    raw_n = int(df_raw["n"].iloc[0])
    fct_n = int(df_fct["n"].iloc[0])
    assert fct_n > 0, "fct_sessions is empty"
    assert fct_n == raw_n, (
        f"fct_sessions row count ({fct_n}) does not match "
        f"raw_ga4_sessions ({raw_n})"
    )


def test_fct_sessions_date_fk_valid():
    """All fct_sessions rows should have a valid date_id (no nulls after ETL)."""
    df = query_df("SELECT COUNT(*) AS n FROM fct_sessions WHERE date_id IS NULL")
    null_count = int(df["n"].iloc[0])
    assert null_count == 0, f"{null_count} rows have NULL date_id in fct_sessions"


def test_fct_sessions_page_fk_valid():
    """All fct_sessions rows should have a valid page_id (no nulls after ETL)."""
    df = query_df("SELECT COUNT(*) AS n FROM fct_sessions WHERE page_id IS NULL")
    null_count = int(df["n"].iloc[0])
    assert null_count == 0, f"{null_count} rows have NULL page_id in fct_sessions"


def test_fct_sessions_date_id_references_dim_dates():
    """Every date_id in fct_sessions must exist in dim_dates."""
    df = query_df("""
        SELECT COUNT(*) AS n
        FROM fct_sessions fs
        LEFT JOIN dim_dates dd ON dd.date_id = fs.date_id
        WHERE dd.date_id IS NULL AND fs.date_id IS NOT NULL
    """)
    orphans = int(df["n"].iloc[0])
    assert orphans == 0, f"{orphans} fct_sessions rows reference non-existent date_id"


def test_fct_sessions_page_id_references_dim_pages():
    """Every page_id in fct_sessions must exist in dim_pages."""
    df = query_df("""
        SELECT COUNT(*) AS n
        FROM fct_sessions fs
        LEFT JOIN dim_pages dp ON dp.page_id = fs.page_id
        WHERE dp.page_id IS NULL AND fs.page_id IS NOT NULL
    """)
    orphans = int(df["n"].iloc[0])
    assert orphans == 0, f"{orphans} fct_sessions rows reference non-existent page_id"


# ── fct_events tests ──────────────────────────────────────────────────────────

def test_fct_events_has_rows():
    """fct_events must have at least as many rows as raw_clickstream_events."""
    df_raw = query_df("SELECT COUNT(*) AS n FROM raw_clickstream_events")
    df_fct = query_df("SELECT COUNT(*) AS n FROM fct_events")
    raw_n = int(df_raw["n"].iloc[0])
    fct_n = int(df_fct["n"].iloc[0])
    assert fct_n > 0, "fct_events is empty"
    assert fct_n == raw_n, (
        f"fct_events row count ({fct_n}) does not match "
        f"raw_clickstream_events ({raw_n})"
    )


def test_fct_events_date_fk_valid():
    df = query_df("SELECT COUNT(*) AS n FROM fct_events WHERE date_id IS NULL")
    assert int(df["n"].iloc[0]) == 0


def test_fct_events_page_fk_valid():
    df = query_df("SELECT COUNT(*) AS n FROM fct_events WHERE page_id IS NULL")
    assert int(df["n"].iloc[0]) == 0


def test_fct_events_date_id_references_dim_dates():
    df = query_df("""
        SELECT COUNT(*) AS n
        FROM fct_events fe
        LEFT JOIN dim_dates dd ON dd.date_id = fe.date_id
        WHERE dd.date_id IS NULL AND fe.date_id IS NOT NULL
    """)
    assert int(df["n"].iloc[0]) == 0


def test_fct_events_page_id_references_dim_pages():
    df = query_df("""
        SELECT COUNT(*) AS n
        FROM fct_events fe
        LEFT JOIN dim_pages dp ON dp.page_id = fe.page_id
        WHERE dp.page_id IS NULL AND fe.page_id IS NOT NULL
    """)
    assert int(df["n"].iloc[0]) == 0


def test_fct_events_event_names_are_known():
    """event_name values should be one of the expected types."""
    df = query_df("SELECT DISTINCT event_name FROM fct_events")
    known = {"click", "scroll", "pageview", "form_submit", "purchase", "custom"}
    actual = set(df["event_name"].dropna().tolist())
    unknown = actual - known
    assert len(unknown) == 0, f"Unexpected event_names: {unknown}"


# ── dim_pages tests ───────────────────────────────────────────────────────────

def test_dim_pages_has_rows():
    df = query_df("SELECT COUNT(*) AS n FROM dim_pages")
    assert int(df["n"].iloc[0]) > 0, "dim_pages is empty"


def test_dim_pages_url_unique():
    df = query_df("""
        SELECT COUNT(*) AS total, COUNT(DISTINCT url) AS unique_urls FROM dim_pages
    """)
    total = int(df["total"].iloc[0])
    unique = int(df["unique_urls"].iloc[0])
    assert total == unique, f"dim_pages has {total - unique} duplicate URL entries"


def test_dim_pages_has_page_titles():
    """At least 50% of dim_pages rows should have a page_title."""
    df = query_df("""
        SELECT
            COUNT(*) AS total,
            COUNT(page_title) AS with_title
        FROM dim_pages
    """)
    total = int(df["total"].iloc[0])
    with_title = int(df["with_title"].iloc[0])
    pct = with_title / total if total > 0 else 0
    assert pct >= 0.5, f"Only {pct*100:.0f}% of dim_pages rows have page_title"


# ── run_all_transforms integration test ──────────────────────────────────────

def test_run_all_transforms_completes():
    """run_all_transforms.run() should complete without error and return counts."""
    from sql.run_all_transforms import run as run_transforms
    result = run_transforms(verbose=False)
    assert "final_counts" in result
    assert result["final_counts"]["fct_sessions"] > 0
    assert result["final_counts"]["fct_events"] > 0
    assert result["final_counts"]["dim_pages"] > 0
    assert result["total_elapsed"] > 0
