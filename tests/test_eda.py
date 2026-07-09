"""Unit tests for Day 26 EDA: raw tables, dim_dates, SQL views, and generate_summary."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ── 1. All 4 raw tables have data ─────────────────────────────────────────────

def test_raw_ga4_sessions_has_data():
    from utils.db import query_df
    df = query_df("SELECT COUNT(*) n FROM raw_ga4_sessions")
    assert int(df["n"].iloc[0]) > 0, "raw_ga4_sessions is empty"


def test_raw_server_logs_has_data():
    from utils.db import query_df
    df = query_df("SELECT COUNT(*) n FROM raw_server_logs")
    assert int(df["n"].iloc[0]) > 0, "raw_server_logs is empty"


def test_raw_clickstream_events_has_data():
    from utils.db import query_df
    df = query_df("SELECT COUNT(*) n FROM raw_clickstream_events")
    assert int(df["n"].iloc[0]) > 0, "raw_clickstream_events is empty"


def test_raw_scrape_pages_has_data():
    from utils.db import query_df
    df = query_df("SELECT COUNT(*) n FROM raw_scrape_pages")
    assert int(df["n"].iloc[0]) > 0, "raw_scrape_pages is empty"


# ── 2. dim_dates has enough rows to cover all raw data ───────────────────────
# Extended to 2026 in Day 28 to match mock data (which spans 2026).

def test_dim_dates_row_count():
    from utils.db import query_df
    df = query_df("SELECT COUNT(*) n FROM dim_dates")
    assert int(df["n"].iloc[0]) >= 1096, (
        f"Expected at least 1096 dim_dates rows, got {df['n'].iloc[0]}"
    )


def test_dim_dates_date_range():
    from utils.db import query_df
    df = query_df("SELECT MIN(full_date)::TEXT mn, MAX(full_date)::TEXT mx FROM dim_dates")
    assert df["mn"].iloc[0] == "2023-01-01"
    # dim_dates now extends to cover 2026 raw data
    from datetime import date
    assert df["mx"].iloc[0] >= "2026-01-01", (
        f"dim_dates max date {df['mx'].iloc[0]} should cover 2026 raw data"
    )


# ── 3. All SQL views return data (no crash) ───────────────────────────────────

VIEWS = [
    "vw_daily_traffic",
    "vw_channel_performance",
    "vw_new_vs_returning",
    "vw_conversions",
    "vw_top_pages",
    "vw_scroll_depth",
    "vw_engagement_events",
    "vw_seo",
    "vw_behavior",
    "vw_device_breakdown",
    "vw_traffic_by_hour",
]


@pytest.mark.parametrize("view", VIEWS)
def test_view_executes_without_error(view):
    from utils.db import query_df
    df = query_df(f"SELECT * FROM {view} LIMIT 5")
    assert df is not None, f"{view} returned None"
    # Views may be empty with mock data but should not raise
    assert hasattr(df, "columns"), f"{view} did not return a DataFrame"


# ── 4. generate_summary.py runs without errors ────────────────────────────────

def test_generate_summary_runs():
    script = ROOT / "analysis" / "generate_summary.py"
    assert script.exists(), f"generate_summary.py not found at {script}"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"generate_summary.py exited with code {result.returncode}.\n"
        f"stderr: {result.stderr[:500]}"
    )
    assert "SUMMARY REPORT" in result.stdout, (
        "Expected 'SUMMARY REPORT' in output"
    )


# ── 5. platform_summary.txt is created ────────────────────────────────────────

def test_platform_summary_file_exists():
    summary_path = ROOT / "data" / "processed" / "platform_summary.txt"
    assert summary_path.exists(), f"platform_summary.txt not found at {summary_path}"
    content = summary_path.read_text(encoding="utf-8")
    assert "SUMMARY REPORT" in content
    assert len(content) > 200, "platform_summary.txt appears too short"


# ── 6. EDA plots directory has expected plots ─────────────────────────────────

def test_eda_plots_directory_exists():
    plot_dir = ROOT / "data" / "processed" / "eda_plots"
    assert plot_dir.exists(), f"eda_plots directory not found at {plot_dir}"
    pngs = list(plot_dir.glob("*.png"))
    assert len(pngs) >= 10, f"Expected at least 10 EDA plots, found {len(pngs)}"


# ── 7. DATA_DICTIONARY.md exists and has required sections ────────────────────

def test_data_dictionary_exists():
    dd = ROOT / "data" / "DATA_DICTIONARY.md"
    assert dd.exists(), f"DATA_DICTIONARY.md not found at {dd}"
    content = dd.read_text(encoding="utf-8")
    for section in ["raw_ga4_sessions", "raw_server_logs", "dim_dates", "SQL Views", "AI Features"]:
        assert section in content, f"DATA_DICTIONARY.md missing section: {section}"
