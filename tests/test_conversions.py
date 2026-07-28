"""
Tests for conversion data quality and conversion_calculator utilities.
Covers: vw_conversions, vw_funnel, and utils/conversion_calculator.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from utils.db import query_df
from utils.conversion_calculator import (
    calculate_cvr,
    calculate_revenue_per_session,
    calculate_goal_value,
    calculate_roas,
    format_conversion_metrics,
)


# ── vw_conversions data tests ─────────────────────────────────────────────────

class TestVwConversionsData:
    """vw_conversions view returns valid, non-negative conversion metrics."""

    def test_returns_data(self):
        df = query_df("SELECT * FROM vw_conversions LIMIT 5")
        assert len(df) >= 1, "vw_conversions must return at least one row"

    def test_sessions_positive(self):
        df = query_df("SELECT COUNT(*) AS n FROM vw_conversions WHERE sessions <= 0")
        assert int(df["n"].iloc[0]) == 0, "sessions must be > 0 in all rows"

    def test_goal_completions_non_negative(self):
        df = query_df("SELECT COUNT(*) AS n FROM vw_conversions WHERE goal_completions < 0")
        assert int(df["n"].iloc[0]) == 0, "goal_completions must be >= 0"

    def test_revenue_non_negative(self):
        df = query_df("SELECT COUNT(*) AS n FROM vw_conversions WHERE revenue < 0")
        assert int(df["n"].iloc[0]) == 0, "revenue must be >= 0"

    def test_cvr_between_0_and_100(self):
        df = query_df(
            "SELECT COUNT(*) AS n FROM vw_conversions "
            "WHERE ROUND(goal_completions::NUMERIC / NULLIF(sessions, 0) * 100, 4) NOT BETWEEN 0 AND 100"
        )
        assert int(df["n"].iloc[0]) == 0, "CVR must be in [0, 100] for all rows"

    def test_revenue_positive_when_completions_positive(self):
        df = query_df(
            "SELECT COUNT(*) AS n FROM vw_conversions "
            "WHERE goal_completions > 0 AND revenue <= 0"
        )
        assert int(df["n"].iloc[0]) == 0, "revenue must be > 0 when goal_completions > 0"

    def test_session_date_not_null(self):
        df = query_df("SELECT COUNT(*) AS n FROM vw_conversions WHERE session_date IS NULL")
        assert int(df["n"].iloc[0]) == 0, "session_date must not be NULL"

    def test_channel_grouping_not_null(self):
        df = query_df("SELECT COUNT(*) AS n FROM vw_conversions WHERE channel_grouping IS NULL")
        assert int(df["n"].iloc[0]) == 0, "channel_grouping must not be NULL"


# ── vw_funnel stage tests ─────────────────────────────────────────────────────

class TestVwFunnelStages:
    """vw_funnel has the expected structure and monotone-decreasing user counts."""

    def test_returns_data(self):
        df = query_df("SELECT * FROM vw_funnel")
        assert len(df) >= 1, "vw_funnel must return at least one row"

    def test_has_five_stages(self):
        df = query_df("SELECT COUNT(*) AS n FROM vw_funnel")
        assert int(df["n"].iloc[0]) == 5, "vw_funnel must have exactly 5 stages"

    def test_users_reached_non_negative(self):
        df = query_df("SELECT COUNT(*) AS n FROM vw_funnel WHERE users_reached < 0")
        assert int(df["n"].iloc[0]) == 0, "users_reached must be >= 0"

    def test_drop_off_count_non_negative(self):
        df = query_df("SELECT COUNT(*) AS n FROM vw_funnel WHERE drop_off_count < 0")
        assert int(df["n"].iloc[0]) == 0, "drop_off_count must be >= 0"

    def test_monotone_decreasing_users(self):
        df = query_df("SELECT users_reached FROM vw_funnel ORDER BY stage_order")
        vals = df["users_reached"].tolist()
        for i in range(1, len(vals)):
            assert vals[i] <= vals[i - 1], (
                f"Funnel not monotone at stage {i + 1}: {vals[i]} > {vals[i - 1]}"
            )


# ── conversion_calculator unit tests ─────────────────────────────────────────

class TestCalculateCvr:
    """calculate_cvr returns a fraction in [0.0, 1.0]."""

    def test_typical(self):
        assert calculate_cvr(1000, 30) == pytest.approx(0.03)

    def test_zero_sessions_returns_zero(self):
        assert calculate_cvr(0, 10) == 0.0

    def test_zero_conversions(self):
        assert calculate_cvr(500, 0) == 0.0

    def test_result_between_0_and_1(self):
        result = calculate_cvr(200, 7)
        assert 0.0 <= result <= 1.0

    def test_perfect_conversion(self):
        assert calculate_cvr(100, 100) == 1.0

    def test_negative_sessions_returns_zero(self):
        assert calculate_cvr(-50, 5) == 0.0


class TestCalculateRevenuePerSession:
    """calculate_revenue_per_session returns non-negative float."""

    def test_typical(self):
        assert calculate_revenue_per_session(1500.0, 1000) == pytest.approx(1.5)

    def test_zero_sessions(self):
        assert calculate_revenue_per_session(1000.0, 0) == 0.0

    def test_zero_revenue(self):
        assert calculate_revenue_per_session(0.0, 500) == 0.0

    def test_result_non_negative(self):
        assert calculate_revenue_per_session(250.0, 50) >= 0.0


class TestCalculateGoalValue:
    """calculate_goal_value returns completions × avg_value."""

    def test_typical(self):
        assert calculate_goal_value(30, 50.0) == pytest.approx(1500.0)

    def test_zero_completions(self):
        assert calculate_goal_value(0, 50.0) == 0.0

    def test_zero_avg_value(self):
        assert calculate_goal_value(100, 0.0) == 0.0

    def test_negative_inputs_return_zero(self):
        assert calculate_goal_value(-5, 10.0) == 0.0
        assert calculate_goal_value(5, -10.0) == 0.0


class TestCalculateRoas:
    """calculate_roas returns revenue / ad_spend."""

    def test_typical(self):
        assert calculate_roas(1500.0, 300.0) == pytest.approx(5.0)

    def test_zero_spend_returns_zero(self):
        assert calculate_roas(1500.0, 0.0) == 0.0

    def test_negative_spend_returns_zero(self):
        assert calculate_roas(1000.0, -100.0) == 0.0

    def test_result_non_negative(self):
        assert calculate_roas(200.0, 50.0) >= 0.0


class TestFormatConversionMetrics:
    """format_conversion_metrics enriches dict with computed and formatted fields."""

    def test_returns_dict(self):
        result = format_conversion_metrics({"sessions": 1000, "conversions": 30})
        assert isinstance(result, dict)

    def test_formatted_cvr_present(self):
        result = format_conversion_metrics({"sessions": 1000, "conversions": 30})
        assert "formatted_cvr" in result
        assert result["formatted_cvr"] == "3.00%"

    def test_roas_with_spend(self):
        result = format_conversion_metrics(
            {"sessions": 1000, "conversions": 30, "revenue": 1500, "ad_spend": 300}
        )
        assert result["formatted_roas"] == "5.00x"

    def test_roas_no_spend(self):
        result = format_conversion_metrics({"sessions": 500, "conversions": 10})
        assert result["formatted_roas"] == "N/A"

    def test_cvr_value_between_0_and_1(self):
        result = format_conversion_metrics({"sessions": 200, "conversions": 10})
        assert 0.0 <= result["cvr"] <= 1.0

    def test_revenue_values_positive(self):
        result = format_conversion_metrics(
            {"sessions": 100, "conversions": 5, "revenue": 250.0, "avg_goal_value": 50.0}
        )
        assert result["total_goal_value"] >= 0.0
        assert result["revenue_per_session"] >= 0.0

    def test_original_keys_preserved(self):
        inp = {"sessions": 500, "conversions": 15, "custom_field": "hello"}
        result = format_conversion_metrics(inp)
        assert result["custom_field"] == "hello"
