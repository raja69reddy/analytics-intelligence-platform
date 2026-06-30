"""
Tests for page behavior SQL views: vw_top_pages, vw_page_performance,
vw_error_pages, vw_scroll_depth, vw_engagement_events.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.db import query_df


class TestVwTopPages:
    VIEW = "vw_top_pages"
    REQUIRED_COLS = {
        "url", "page_title", "page_section", "total_requests",
        "unique_visitors", "avg_response_time_ms", "error_rate_pct", "last_visited",
    }

    def test_view_exists_and_returns_data(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 10")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_ordered_by_total_requests_desc(self):
        df = query_df(f"SELECT total_requests FROM {self.VIEW}")
        assert list(df["total_requests"]) == sorted(df["total_requests"], reverse=True)

    def test_no_negative_request_counts(self):
        df = query_df(f"SELECT * FROM {self.VIEW} WHERE total_requests < 0")
        assert len(df) == 0


class TestVwPagePerformance:
    VIEW = "vw_page_performance"
    REQUIRED_COLS = {
        "url", "total_requests", "avg_response_time_ms", "p95_response_time_ms",
        "fast_requests", "normal_requests", "slow_requests",
    }

    def test_view_exists_and_returns_data(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 10")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_p95_gte_avg(self):
        df = query_df(
            f"SELECT * FROM {self.VIEW} WHERE p95_response_time_ms < avg_response_time_ms"
        )
        assert len(df) == 0, "p95 should be >= avg response time"

    def test_fast_normal_slow_sum_to_total(self):
        df = query_df(
            f"SELECT * FROM {self.VIEW} "
            f"WHERE fast_requests + normal_requests + slow_requests != total_requests"
        )
        assert len(df) == 0, "fast + normal + slow != total on some rows"


class TestVwErrorPages:
    VIEW = "vw_error_pages"
    REQUIRED_COLS = {
        "url", "total_requests", "errors_4xx", "errors_5xx",
        "total_errors", "error_rate_pct",
    }

    def test_view_exists_and_returns_data(self):
        df = query_df(f"SELECT * FROM {self.VIEW}")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_all_rows_have_errors(self):
        df = query_df(f"SELECT * FROM {self.VIEW} WHERE total_errors = 0")
        assert len(df) == 0, "vw_error_pages should only contain pages with errors"

    def test_4xx_plus_5xx_le_total_errors(self):
        df = query_df(
            f"SELECT * FROM {self.VIEW} WHERE errors_4xx + errors_5xx > total_errors"
        )
        assert len(df) == 0, "4xx + 5xx should not exceed total_errors"


class TestVwScrollDepth:
    VIEW = "vw_scroll_depth"
    REQUIRED_COLS = {
        "page_url", "scroll_events", "avg_scroll_depth_pct",
        "bucket_0_25", "bucket_25_50", "bucket_50_75", "bucket_75_100",
    }

    def test_view_exists_and_returns_data(self):
        df = query_df(f"SELECT * FROM {self.VIEW}")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_avg_scroll_depth_between_0_and_100(self):
        df = query_df(
            f"SELECT * FROM {self.VIEW} "
            f"WHERE avg_scroll_depth_pct < 0 OR avg_scroll_depth_pct > 100"
        )
        assert len(df) == 0, "avg_scroll_depth_pct out of range [0, 100]"

    def test_bucket_counts_sum_to_scroll_events(self):
        df = query_df(
            f"SELECT * FROM {self.VIEW} "
            f"WHERE bucket_0_25 + bucket_25_50 + bucket_50_75 + bucket_75_100 != scroll_events"
        )
        assert len(df) == 0, "bucket counts do not sum to scroll_events"


class TestVwEngagementEvents:
    VIEW = "vw_engagement_events"
    REQUIRED_COLS = {
        "page_url", "total_events", "click_events", "scroll_events",
        "pageview_events", "form_submit_events",
    }
    ALL_EVENT_TYPES = {"click", "scroll", "pageview", "form_submit"}

    def test_view_exists_and_returns_data(self):
        df = query_df(f"SELECT * FROM {self.VIEW}")
        assert len(df) >= 1

    def test_required_columns(self):
        df = query_df(f"SELECT * FROM {self.VIEW} LIMIT 1")
        missing = self.REQUIRED_COLS - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_all_event_types_present_in_source(self):
        df = query_df("SELECT DISTINCT event_name FROM raw_clickstream_events")
        present = set(df["event_name"].tolist())
        assert self.ALL_EVENT_TYPES == present, f"Expected event types {self.ALL_EVENT_TYPES}, got {present}"

    def test_event_columns_sum_to_total(self):
        df = query_df(
            f"SELECT * FROM {self.VIEW} "
            f"WHERE click_events + scroll_events + pageview_events + form_submit_events != total_events"
        )
        assert len(df) == 0, "event type columns do not sum to total_events"
