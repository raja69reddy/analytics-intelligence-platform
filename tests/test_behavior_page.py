"""
Tests for behavior page data: vw_top_pages, vw_scroll_depth,
vw_engagement_events, and funnel stage data from raw_clickstream_events.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.db import query_df


class TestVwTopPagesBehavior:
    """Verify vw_top_pages returns data suitable for the behavior page."""

    def test_returns_data(self):
        df = query_df("SELECT * FROM vw_top_pages LIMIT 10")
        assert len(df) >= 1, "vw_top_pages should return at least one row"

    def test_required_columns(self):
        df = query_df("SELECT * FROM vw_top_pages LIMIT 1")
        required = {"url", "total_requests", "avg_response_time_ms", "error_rate_pct"}
        missing = required - set(df.columns)
        assert not missing, f"vw_top_pages missing columns: {missing}"

    def test_sorted_by_total_requests_desc(self):
        df = query_df("SELECT total_requests FROM vw_top_pages")
        assert list(df["total_requests"]) == sorted(df["total_requests"], reverse=True)

    def test_no_null_urls(self):
        df = query_df("SELECT * FROM vw_top_pages WHERE url IS NULL")
        assert len(df) == 0, "vw_top_pages should have no null URLs"


class TestVwScrollDepthValues:
    """Verify scroll depth values are valid percentages and buckets are consistent."""

    def test_returns_data(self):
        df = query_df("SELECT * FROM vw_scroll_depth")
        assert len(df) >= 1

    def test_avg_scroll_depth_in_range(self):
        df = query_df(
            "SELECT * FROM vw_scroll_depth "
            "WHERE avg_scroll_depth_pct < 0 OR avg_scroll_depth_pct > 100"
        )
        assert len(df) == 0, "avg_scroll_depth_pct must be between 0 and 100"

    def test_buckets_sum_to_total(self):
        df = query_df(
            "SELECT * FROM vw_scroll_depth "
            "WHERE bucket_0_25 + bucket_25_50 + bucket_50_75 + bucket_75_100 != scroll_events"
        )
        assert len(df) == 0, "bucket counts must sum to scroll_events"

    def test_scroll_events_positive(self):
        df = query_df("SELECT * FROM vw_scroll_depth WHERE scroll_events <= 0")
        assert len(df) == 0, "scroll_events should be > 0 for all rows"


class TestVwEngagementEventsTypes:
    """Verify all expected event types appear in vw_engagement_events."""

    ALL_EVENT_TYPES = {"click", "scroll", "pageview", "form_submit"}

    def test_returns_data(self):
        df = query_df("SELECT * FROM vw_engagement_events LIMIT 5")
        assert len(df) >= 1

    def test_all_event_types_in_source(self):
        df = query_df("SELECT DISTINCT event_name FROM raw_clickstream_events")
        present = set(df["event_name"].tolist())
        assert self.ALL_EVENT_TYPES.issubset(present), (
            f"Expected event types {self.ALL_EVENT_TYPES} not all present; got {present}"
        )

    def test_event_columns_non_negative(self):
        df = query_df(
            "SELECT * FROM vw_engagement_events "
            "WHERE click_events < 0 OR scroll_events < 0 "
            "OR pageview_events < 0 OR form_submit_events < 0"
        )
        assert len(df) == 0, "Event count columns should be non-negative"

    def test_total_events_gte_sum_of_types(self):
        df = query_df(
            "SELECT * FROM vw_engagement_events "
            "WHERE total_events < click_events + scroll_events + pageview_events + form_submit_events"
        )
        assert len(df) == 0, "total_events must be >= sum of individual event type columns"


class TestFunnelData:
    """Verify funnel data derived from raw_clickstream_events has the right shape."""

    FUNNEL_STAGES = ["homepage", "product_page", "add_to_cart", "checkout", "purchase"]

    def _funnel_df(self):
        return query_df("""
WITH homepage AS (
    SELECT DISTINCT session_id FROM raw_clickstream_events
    WHERE event_name = 'pageview' AND page_url = '/'
),
product AS (
    SELECT DISTINCT session_id FROM raw_clickstream_events
    WHERE event_name = 'pageview' AND page_url IN ('/products/', '/pricing/')
),
cart AS (
    SELECT DISTINCT session_id FROM raw_clickstream_events
    WHERE event_name = 'click' AND page_url IN ('/products/', '/pricing/')
),
checkout AS (
    SELECT DISTINCT session_id FROM raw_clickstream_events
    WHERE event_name = 'form_submit'
)
SELECT
    (SELECT COUNT(*) FROM homepage) AS homepage,
    (SELECT COUNT(*) FROM product)  AS product_page,
    (SELECT COUNT(*) FROM cart)     AS add_to_cart,
    (SELECT COUNT(*) FROM checkout) AS checkout,
    ROUND((SELECT COUNT(*) FROM checkout) * 0.35) AS purchase
""")

    def test_funnel_returns_one_row(self):
        df = self._funnel_df()
        assert len(df) == 1, "Funnel query should return exactly one row"

    def test_funnel_has_all_stages(self):
        df = self._funnel_df()
        missing = set(self.FUNNEL_STAGES) - set(df.columns)
        assert not missing, f"Funnel is missing columns: {missing}"

    def test_funnel_values_non_negative(self):
        df = self._funnel_df()
        for stage in self.FUNNEL_STAGES:
            assert int(df[stage].iloc[0]) >= 0, f"Funnel stage {stage} is negative"

    def test_funnel_top_stage_gte_later_stages(self):
        df = self._funnel_df()
        homepage = int(df["homepage"].iloc[0])
        checkout = int(df["checkout"].iloc[0])
        assert homepage >= checkout, "Homepage visits should be >= checkout sessions"
