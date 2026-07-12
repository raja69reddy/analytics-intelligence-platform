"""
Tests for all SQL views: existence, non-empty results, correct columns, date range.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.db import query_df  # noqa: E402


# ---------------------------------------------------------------------------
# vw_traffic
# ---------------------------------------------------------------------------
class TestVwTraffic:
    VIEW = "vw_traffic"
    REQUIRED_COLS = {
        "session_date",
        "year",
        "month",
        "channel_grouping",
        "source",
        "medium",
        "total_sessions",
        "new_users",
        "total_pageviews",
        "avg_bounce_rate",
        "avg_session_duration",
    }

    def test_view_exists(self):
        df = query_df(f"SELECT COUNT(*) AS n FROM {self.VIEW}")
        assert df is not None

    def test_returns_rows(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 10")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns in {self.VIEW}: {missing}"

    def test_date_range_is_valid(self):
        df = query_df(
            f"SELECT MIN(session_date) AS mn, MAX(session_date) AS mx FROM {self.VIEW}"
        )
        assert df["mn"].iloc[0] <= df["mx"].iloc[0]


# ---------------------------------------------------------------------------
# vw_daily_traffic
# ---------------------------------------------------------------------------
class TestVwDailyTraffic:
    VIEW = "vw_daily_traffic"
    REQUIRED_COLS = {
        "session_date",
        "total_sessions",
        "new_users",
        "total_pageviews",
        "bounce_rate_pct",
        "avg_session_duration",
        "sessions_7day_avg",
    }

    def test_view_exists(self):
        df = query_df(f"SELECT COUNT(*) AS n FROM {self.VIEW}")
        assert df is not None

    def test_returns_rows(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 10")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns in {self.VIEW}: {missing}"

    def test_rolling_avg_is_positive(self):
        df = query_df(f"SELECT * FROM {self.VIEW}")
        assert (df["sessions_7day_avg"] > 0).all()


# ---------------------------------------------------------------------------
# vw_channel_performance
# ---------------------------------------------------------------------------
class TestVwChannelPerformance:
    VIEW = "vw_channel_performance"
    REQUIRED_COLS = {
        "channel_grouping",
        "total_sessions",
        "total_new_users",
        "total_pageviews",
        "avg_session_duration",
        "bounce_rate_pct",
        "channel_share_pct",
    }

    def test_view_exists(self):
        df = query_df(f"SELECT COUNT(*) AS n FROM {self.VIEW}")
        assert df is not None

    def test_returns_rows(self):
        df = query_df(f"SELECT * FROM {self.VIEW}")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns in {self.VIEW}: {missing}"

    def test_share_pct_sums_to_100(self):
        df = query_df(f"SELECT SUM(channel_share_pct) AS total FROM {self.VIEW}")
        total = float(df["total"].iloc[0])
        assert abs(total - 100.0) < 1.0, f"channel_share_pct sums to {total}"


# ---------------------------------------------------------------------------
# vw_new_vs_returning
# ---------------------------------------------------------------------------
class TestVwNewVsReturning:
    VIEW = "vw_new_vs_returning"
    REQUIRED_COLS = {
        "session_date",
        "total_sessions",
        "new_user_sessions",
        "returning_user_sessions",
        "new_user_pct",
        "returning_user_pct",
    }

    def test_view_exists(self):
        df = query_df(f"SELECT COUNT(*) AS n FROM {self.VIEW}")
        assert df is not None

    def test_returns_rows(self):
        df = query_df(f"SELECT * FROM {self.VIEW}")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns in {self.VIEW}: {missing}"

    def test_new_plus_returning_equals_total(self):
        df = query_df(
            f"SELECT * FROM {self.VIEW} WHERE new_user_sessions + returning_user_sessions != total_sessions"
        )
        assert len(df) == 0, "new + returning != total on some rows"


# ---------------------------------------------------------------------------
# vw_device_breakdown
# ---------------------------------------------------------------------------
class TestVwDeviceBreakdown:
    VIEW = "vw_device_breakdown"
    REQUIRED_COLS = {
        "device_category",
        "total_sessions",
        "bounce_rate_pct",
        "device_share_pct",
    }

    def test_view_exists(self):
        df = query_df(f"SELECT COUNT(*) AS n FROM {self.VIEW}")
        assert df is not None

    def test_returns_rows(self):
        df = query_df(f"SELECT * FROM {self.VIEW}")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns in {self.VIEW}: {missing}"

    def test_bounce_rate_between_0_and_100(self):
        df = query_df(
            f"SELECT * FROM {self.VIEW} WHERE bounce_rate_pct < 0 OR bounce_rate_pct > 100"
        )
        assert len(df) == 0, "bounce_rate_pct out of range [0,100]"


# ---------------------------------------------------------------------------
# vw_geo_performance
# ---------------------------------------------------------------------------
class TestVwGeoPerformance:
    VIEW = "vw_geo_performance"
    REQUIRED_COLS = {
        "country",
        "total_sessions",
        "bounce_rate_pct",
        "country_share_pct",
    }

    def test_view_exists(self):
        df = query_df(f"SELECT COUNT(*) AS n FROM {self.VIEW}")
        assert df is not None

    def test_returns_rows(self):
        df = query_df(f"SELECT * FROM {self.VIEW}")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns in {self.VIEW}: {missing}"

    def test_max_10_rows(self):
        df = query_df(f"SELECT COUNT(*) AS n FROM {self.VIEW}")
        assert (
            int(df["n"].iloc[0]) <= 10
        ), "vw_geo_performance returned more than 10 rows"
