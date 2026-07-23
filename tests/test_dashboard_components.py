"""
Tests for dashboard/components/*.py and utils/dashboard_metrics.py.

Covers:
- metrics.py: formatting helpers return correct string formats
- charts.py: factory functions return go.Figure; utility functions mutate in place
- tables.py: styling helpers return Styler / DataFrame correctly
- dashboard_metrics.py: accessors return expected Python types (no DB required for
  format tests; DB-dependent tests are skipped when the DB is unreachable)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── helpers ───────────────────────────────────────────────────────────────────

def _db_available() -> bool:
    try:
        from utils.db import query_df
        query_df("SELECT 1 AS ok")
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()
requires_db = pytest.mark.skipif(not DB_AVAILABLE, reason="DB not reachable")


# ══ metrics.py ════════════════════════════════════════════════════════════════

class TestFormatLargeNumber:
    def setup_method(self):
        from dashboard.components.metrics import format_large_number
        self.fn = format_large_number

    def test_millions(self):
        assert self.fn(1_500_000) == "1.5M"

    def test_thousands(self):
        assert self.fn(12_345) == "12.3K"

    def test_under_thousand(self):
        assert self.fn(999) == "999"

    def test_zero(self):
        assert self.fn(0) == "0"


class TestCalculatePeriodChange:
    def setup_method(self):
        from dashboard.components.metrics import calculate_period_change
        self.fn = calculate_period_change

    def test_positive_change(self):
        result = self.fn(110, 100)
        assert result == "+10.0%"

    def test_negative_change(self):
        result = self.fn(90, 100)
        assert result == "-10.0%"

    def test_zero_previous(self):
        result = self.fn(50, 0)
        assert result == "+100%"

    def test_no_change(self):
        result = self.fn(100, 100)
        assert result == "+0.0%"


class TestFormatCurrency:
    def setup_method(self):
        from dashboard.components.metrics import format_currency
        self.fn = format_currency

    def test_basic(self):
        assert self.fn(1234.5) == "$1,235"

    def test_none(self):
        assert self.fn(None) == "$0"


class TestFormatDuration:
    def setup_method(self):
        from dashboard.components.metrics import format_duration
        self.fn = format_duration

    def test_seconds(self):
        assert self.fn(45) == "45s"

    def test_minutes(self):
        assert self.fn(125) == "2m 5s"

    def test_hours(self):
        assert self.fn(3661) == "1h 1m"

    def test_none(self):
        assert self.fn(None) == "--"


# ══ charts.py ═════════════════════════════════════════════════════════════════

class TestChartFactories:
    def setup_method(self):
        from dashboard.components import charts
        self.charts = charts
        self.df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6], "cat": ["a", "b", "c"]})

    def test_line_chart_returns_figure(self):
        fig = self.charts.line_chart(self.df, x="x", y="y")
        assert isinstance(fig, go.Figure)

    def test_bar_chart_returns_figure(self):
        fig = self.charts.bar_chart(self.df, x="x", y="y")
        assert isinstance(fig, go.Figure)

    def test_pie_chart_returns_figure(self):
        fig = self.charts.pie_chart(self.df, names="cat", values="y")
        assert isinstance(fig, go.Figure)

    def test_funnel_chart_returns_figure(self):
        fig = self.charts.funnel_chart(["A", "B", "C"], [100, 60, 30])
        assert isinstance(fig, go.Figure)

    def test_scatter_chart_returns_figure(self):
        fig = self.charts.scatter_chart(self.df, x="x", y="y")
        assert isinstance(fig, go.Figure)


class TestChartUtilities:
    def setup_method(self):
        from dashboard.components import charts
        self.charts = charts
        self.df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        self.fig = self.charts.line_chart(self.df, x="x", y="y")

    def test_add_chart_theme_returns_figure(self):
        result = self.charts.add_chart_theme(self.fig)
        assert isinstance(result, go.Figure)

    def test_add_hover_template_returns_figure(self):
        result = self.charts.add_hover_template(self.fig)
        assert isinstance(result, go.Figure)

    def test_add_range_selector_returns_figure(self):
        result = self.charts.add_range_selector(self.fig)
        assert isinstance(result, go.Figure)
        buttons = result.layout.xaxis.rangeselector.buttons
        labels = [b.label for b in buttons]
        assert "7D" in labels
        assert "30D" in labels
        assert "90D" in labels

    def test_add_reference_line_returns_figure(self):
        result = self.charts.add_reference_line(self.fig, value=5, label="Avg")
        assert isinstance(result, go.Figure)
        assert len(result.layout.shapes) > 0


# ══ tables.py ═════════════════════════════════════════════════════════════════

class TestAddRankColumn:
    def setup_method(self):
        from dashboard.components.tables import add_rank_column
        self.fn = add_rank_column
        self.df = pd.DataFrame({"page": ["/a", "/b", "/c"], "views": [300, 100, 200]})

    def test_prepends_hash_column(self):
        result = self.fn(self.df)
        assert result.columns[0] == "#"

    def test_rank_starts_at_one(self):
        result = self.fn(self.df)
        assert result["#"].iloc[0] == 1

    def test_sort_by_col_descending(self):
        result = self.fn(self.df, col="views", ascending=False)
        assert result["views"].iloc[0] == 300

    def test_does_not_mutate_original(self):
        original_cols = list(self.df.columns)
        self.fn(self.df, col="views")
        assert list(self.df.columns) == original_cols


class TestFormatTableNumbers:
    def setup_method(self):
        from dashboard.components.tables import format_table_numbers
        self.fn = format_table_numbers

    def test_returns_styler(self):
        df = pd.DataFrame({"a": [1, 2], "b": [1.1, 2.2]})
        result = self.fn(df)
        assert hasattr(result, "to_html")

    def test_handles_empty_df(self):
        df = pd.DataFrame({"a": pd.Series([], dtype=int)})
        result = self.fn(df)
        assert result is not None


class TestHighlightSlowPages:
    def setup_method(self):
        from dashboard.components.tables import highlight_slow_pages
        self.fn = highlight_slow_pages

    def test_returns_styler(self):
        df = pd.DataFrame({"avg_response_time_ms": [50, 500, 1500]})
        result = self.fn(df)
        assert hasattr(result, "to_html")


class TestHighlightTopPerformers:
    def setup_method(self):
        from dashboard.components.tables import highlight_top_performers
        self.fn = highlight_top_performers

    def test_returns_styler(self):
        df = pd.DataFrame({"score": [10, 20, 30, 40, 50]})
        result = self.fn(df, col="score", top_n=2)
        assert hasattr(result, "to_html")

    def test_empty_df_returns_styler(self):
        df = pd.DataFrame({"score": pd.Series([], dtype=float)})
        result = self.fn(df, col="score")
        assert result is not None


# ══ dashboard_metrics.py ══════════════════════════════════════════════════════

class TestDashboardMetricsImport:
    """Verify all public functions are importable and callable with no args."""

    def test_import(self):
        from utils import dashboard_metrics  # noqa: F401

    def test_all_functions_exist(self):
        from utils import dashboard_metrics as dm
        for fn_name in (
            "get_total_sessions",
            "get_total_users",
            "get_overall_cvr",
            "get_avg_bounce_rate",
            "get_top_channel",
            "get_top_page",
        ):
            assert callable(getattr(dm, fn_name, None)), f"{fn_name} not callable"


@requires_db
class TestDashboardMetricsDB:
    """DB-dependent metric accessor tests."""

    def setup_method(self):
        from utils.dashboard_metrics import (
            get_total_sessions,
            get_total_users,
            get_overall_cvr,
            get_avg_bounce_rate,
            get_top_channel,
            get_top_page,
        )
        self.fns = {
            "sessions": get_total_sessions,
            "users": get_total_users,
            "cvr": get_overall_cvr,
            "bounce": get_avg_bounce_rate,
            "channel": get_top_channel,
            "page": get_top_page,
        }

    def test_get_total_sessions_returns_int(self):
        result = self.fns["sessions"]()
        assert isinstance(result, int)
        assert result >= 0

    def test_get_total_users_returns_int(self):
        result = self.fns["users"]()
        assert isinstance(result, int)
        assert result >= 0

    def test_get_overall_cvr_returns_float(self):
        result = self.fns["cvr"]()
        assert isinstance(result, float)
        assert 0.0 <= result <= 100.0

    def test_get_avg_bounce_rate_returns_float(self):
        result = self.fns["bounce"]()
        assert isinstance(result, float)
        assert 0.0 <= result <= 100.0

    def test_get_top_channel_returns_string(self):
        result = self.fns["channel"]()
        assert isinstance(result, str)

    def test_get_top_page_returns_string(self):
        result = self.fns["page"]()
        assert isinstance(result, str)
