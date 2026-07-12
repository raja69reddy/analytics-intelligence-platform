"""
Tests for conversions page data: vw_conversions and vw_funnel.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.db import query_df  # noqa: E402


class TestVwConversions:
    """Verify vw_conversions returns valid conversion metrics."""

    def test_returns_data(self):
        df = query_df("SELECT * FROM vw_conversions LIMIT 10")
        assert len(df) >= 1, "vw_conversions should return at least one row"

    def test_required_columns(self):
        df = query_df("SELECT * FROM vw_conversions LIMIT 1")
        required = {
            "session_date",
            "channel_grouping",
            "source",
            "medium",
            "sessions",
            "goal_completions",
            "revenue",
            "conversion_rate_pct",
            "revenue_per_conversion",
        }
        missing = required - set(df.columns)
        assert not missing, f"vw_conversions missing columns: {missing}"

    def test_cvr_between_0_and_100(self):
        df = query_df(
            "SELECT conversion_rate_pct FROM vw_conversions "
            "WHERE conversion_rate_pct < 0 OR conversion_rate_pct > 100"
        )
        assert len(df) == 0, "conversion_rate_pct must be in [0, 100]"

    def test_revenue_non_negative(self):
        df = query_df("SELECT revenue FROM vw_conversions WHERE revenue < 0")
        assert len(df) == 0, "revenue must be non-negative"

    def test_goal_completions_non_negative(self):
        df = query_df(
            "SELECT goal_completions FROM vw_conversions WHERE goal_completions < 0"
        )
        assert len(df) == 0, "goal_completions must be non-negative"

    def test_sessions_positive(self):
        df = query_df("SELECT sessions FROM vw_conversions WHERE sessions <= 0")
        assert len(df) == 0, "sessions must be positive"

    def test_revenue_per_conversion_is_52(self):
        """revenue_per_conversion should be 52.0 for all rows."""
        df = query_df(
            "SELECT revenue_per_conversion FROM vw_conversions "
            "WHERE revenue_per_conversion != 52.0"
        )
        assert len(df) == 0, "revenue_per_conversion must be 52.0 for all rows"

    def test_revenue_positive_when_completions_positive(self):
        """Revenue should be > 0 whenever goal_completions > 0."""
        df = query_df(
            "SELECT goal_completions, revenue FROM vw_conversions "
            "WHERE goal_completions > 0 AND revenue <= 0"
        )
        assert len(df) == 0, "Revenue must be positive when goal_completions > 0"

    def test_channel_groupings_known(self):
        df = query_df("SELECT DISTINCT channel_grouping FROM vw_conversions")
        known = {
            "Email",
            "Paid Search",
            "Organic Search",
            "Direct",
            "Referral",
            "Social",
        }
        unexpected = set(df["channel_grouping"]) - known
        assert not unexpected, f"Unexpected channel groupings: {unexpected}"


class TestVwFunnel:
    """Verify vw_funnel returns correct funnel stage structure."""

    def test_returns_data(self):
        df = query_df("SELECT * FROM vw_funnel")
        assert len(df) >= 1, "vw_funnel should return at least one row"

    def test_has_five_stages(self):
        df = query_df("SELECT COUNT(*) AS cnt FROM vw_funnel")
        assert int(df["cnt"].iloc[0]) == 5, "vw_funnel should have exactly 5 stages"

    def test_required_columns(self):
        df = query_df("SELECT * FROM vw_funnel LIMIT 1")
        required = {
            "stage_order",
            "stage_name",
            "users_reached",
            "drop_off_count",
            "drop_off_pct",
            "completion_rate_pct",
        }
        missing = required - set(df.columns)
        assert not missing, f"vw_funnel missing columns: {missing}"

    def test_users_reached_non_negative(self):
        df = query_df("SELECT users_reached FROM vw_funnel WHERE users_reached < 0")
        assert len(df) == 0, "users_reached must be non-negative"

    def test_monotone_decreasing(self):
        df = query_df("SELECT users_reached FROM vw_funnel ORDER BY stage_order")
        values = df["users_reached"].tolist()
        for i in range(1, len(values)):
            assert values[i] <= values[i - 1], (
                f"Funnel not monotone at stage {i + 1}: "
                f"{values[i]} > {values[i - 1]}"
            )

    def test_completion_rate_first_stage_100(self):
        df = query_df(
            "SELECT completion_rate_pct FROM vw_funnel ORDER BY stage_order LIMIT 1"
        )
        assert (
            float(df["completion_rate_pct"].iloc[0]) == 100.0
        ), "First funnel stage completion_rate_pct should be 100.0"

    def test_drop_off_count_non_negative(self):
        df = query_df("SELECT drop_off_count FROM vw_funnel WHERE drop_off_count < 0")
        assert len(df) == 0, "drop_off_count must be non-negative"

    def test_stage_names_correct(self):
        df = query_df("SELECT stage_name FROM vw_funnel ORDER BY stage_order")
        expected = [
            "All Sessions",
            "Entry Intent",
            "Exploration",
            "Engaged",
            "Converted",
        ]
        assert (
            df["stage_name"].tolist() == expected
        ), f"Stage names mismatch: {df['stage_name'].tolist()}"
