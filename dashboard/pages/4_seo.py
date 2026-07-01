"""SEO & Content Performance dashboard page."""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.filters import get_date_filter, get_page_filter
from utils.db import query_df

st.set_page_config(page_title="SEO & Content", page_icon="🔍", layout="wide")
st.title("🔍 SEO & Content Performance")

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("SEO Filters")
    start_date, end_date = get_date_filter()
    page_search = get_page_filter()

start_str = start_date.isoformat()
end_str   = end_date.isoformat()

# ── KPI cards ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _load_kpis():
    organic = query_df(
        "SELECT SUM(organic_sessions) AS total_organic_sessions, "
        "ROUND(AVG(word_count)) AS avg_word_count, "
        "COUNT(CASE WHEN missing_meta_description THEN 1 END) AS missing_meta "
        "FROM vw_seo"
    )
    load_time = query_df(
        "SELECT ROUND(AVG(load_time_ms)) AS avg_load_ms FROM raw_scrape_pages WHERE http_status = 200"
    )
    return organic, load_time

with st.spinner("Loading KPIs..."):
    try:
        _organic_kpi, _load_kpi = _load_kpis()
        total_organic = int(_organic_kpi["total_organic_sessions"].iloc[0] or 0)
        avg_word_count = int(_organic_kpi["avg_word_count"].iloc[0] or 0)
        missing_meta = int(_organic_kpi["missing_meta"].iloc[0] or 0)
        avg_load_ms = int(_load_kpi["avg_load_ms"].iloc[0] or 0)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Organic Sessions", f"{total_organic:,}")
        col2.metric("Avg Page Load Time", f"{avg_load_ms:,} ms",
                    delta=None,
                    help="Average load time across all crawled pages (200 status only)")
        col3.metric("Pages Missing Meta Description", f"{missing_meta}")
        col4.metric("Avg Word Count per Page", f"{avg_word_count:,}")
    except Exception as exc:
        st.error(f"Could not load KPIs: {exc}")

st.divider()

# ── Word count vs engagement scatter ─────────────────────────────────────────
st.subheader("Word Count vs Engagement")

@st.cache_data(ttl=300)
def _load_wc_scatter():
    return query_df(
        "SELECT s.url, s.word_count, s.organic_sessions, "
        "s.organic_pageviews AS pageviews, "
        "s.avg_session_duration_s, "
        "ROUND(s.organic_bounces::NUMERIC / NULLIF(s.organic_sessions, 0) * 100, 2) AS bounce_rate_pct "
        "FROM vw_seo s "
        "WHERE s.word_count IS NOT NULL AND s.word_count > 0"
    )

with st.spinner("Loading scatter data..."):
    try:
        import plotly.express as px
        import numpy as np

        _wc_df = _load_wc_scatter()
        if _wc_df.empty:
            st.info("No data available for scatter plot.")
        else:
            _wc_df["bubble_size"] = (_wc_df["pageviews"].fillna(1).clip(lower=1))

            fig_scatter = px.scatter(
                _wc_df,
                x="word_count",
                y="avg_session_duration_s",
                size="bubble_size",
                color="bounce_rate_pct",
                hover_name="url",
                hover_data={"word_count": True, "organic_sessions": True, "bubble_size": False},
                labels={
                    "word_count": "Word Count",
                    "avg_session_duration_s": "Avg Session Duration (s)",
                    "bounce_rate_pct": "Bounce Rate %",
                },
                title="Word Count vs Engagement (bubble = pageviews, color = bounce rate)",
                color_continuous_scale="RdYlGn_r",
                trendline="ols",
            )
            fig_scatter.update_layout(height=450)
            st.plotly_chart(fig_scatter, use_container_width=True)
            st.caption("Trend line shows relationship between content length and user engagement.")
    except Exception as exc:
        st.error(f"Could not render scatter plot: {exc}")

st.divider()

# ── Top organic landing pages ─────────────────────────────────────────────────
st.subheader("Top Organic Landing Pages")

@st.cache_data(ttl=300)
def _load_organic_pages(page_filter: str):
    sql = (
        "SELECT url, title, word_count, organic_sessions, organic_pageviews, "
        "avg_session_duration_s, "
        "ROUND(organic_bounces::NUMERIC / NULLIF(organic_sessions, 0) * 100, 2) AS bounce_rate_pct "
        "FROM vw_seo "
        "WHERE organic_sessions > 0 "
        + (f"AND url ILIKE '%{page_filter}%' " if page_filter else "")
        + "ORDER BY organic_sessions DESC LIMIT 20"
    )
    return query_df(sql)

_search = st.text_input("Search pages", value=page_search, placeholder="/blog/")

with st.spinner("Loading organic pages..."):
    try:
        _pages_df = _load_organic_pages(_search)
        if _pages_df.empty:
            st.info("No organic landing pages found with the current filter.")
        else:
            def _highlight_top3(row):
                color = "background-color: #d4edda" if row.name < 3 else ""
                return [color] * len(row)

            styled = _pages_df.style.apply(_highlight_top3, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(_pages_df)} pages | Top 3 highlighted in green")
    except Exception as exc:
        st.error(f"Could not load organic pages: {exc}")

st.divider()
