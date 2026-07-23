"""SEO & Content Performance dashboard page."""

import os
import sys
from datetime import timedelta

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.filters import get_date_filter, get_page_filter
from dashboard.components.metrics import calculate_period_change, display_4_kpi_row
from dashboard.components.tables import add_rank_column
from utils.db import query_df

st.set_page_config(page_title="SEO & Content", page_icon="🔍", layout="wide")
st.title("🔍 SEO & Content Performance")

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("SEO Filters")
    start_date, end_date = get_date_filter()
    page_search = get_page_filter()

start_str = start_date.isoformat()
end_str = end_date.isoformat()

# ── DB connectivity guard ─────────────────────────────────────────────────────
try:
    _check = query_df("SELECT 1 AS ok")
except Exception as _db_exc:
    st.error(
        "**Database connection failed.** Check that PostgreSQL is running and your `.env` credentials are correct.\n\n"
        f"Error: `{_db_exc}`"
    )
    st.stop()

# ── KPI cards — 4 metrics, organic sessions with % change vs previous period ──


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


@st.cache_data(ttl=300)
def _load_organic_sessions(start: str, end: str) -> int:
    df = query_df(
        "SELECT COALESCE(SUM(sessions), 0) AS n FROM raw_ga4_sessions "
        "WHERE channel_grouping ILIKE '%organic%' "
        "AND session_date BETWEEN :s AND :e",
        params={"s": start, "e": end},
    )
    return int(df["n"].iloc[0] or 0)


with st.spinner("Loading KPIs..."):
    try:
        _organic_kpi, _load_kpi = _load_kpis()
        avg_word_count = int(_organic_kpi["avg_word_count"].iloc[0] or 0)
        missing_meta = int(_organic_kpi["missing_meta"].iloc[0] or 0)
        avg_load_ms = int(_load_kpi["avg_load_ms"].iloc[0] or 0)

        _seo_period_days = (end_date - start_date).days + 1
        _seo_prev_start = start_date - timedelta(days=_seo_period_days)
        _seo_prev_end = start_date - timedelta(days=1)

        curr_organic = _load_organic_sessions(start_str, end_str)
        prev_organic = _load_organic_sessions(
            _seo_prev_start.isoformat(), _seo_prev_end.isoformat()
        )

        display_4_kpi_row(
            {
                "title": "Total Organic Sessions",
                "value": f"{curr_organic:,}",
                "delta": calculate_period_change(curr_organic, prev_organic),
                "icon": "🔍",
            },
            {
                "title": "Avg Page Load Time",
                "value": f"{avg_load_ms:,} ms",
                "icon": "⚡",
            },
            {
                "title": "Missing Meta Description",
                "value": str(missing_meta),
                "color": "inverse",
                "icon": "⚠️",
            },
            {
                "title": "Avg Word Count",
                "value": f"{avg_word_count:,}",
                "icon": "📝",
            },
        )
        st.caption(
            f"Organic sessions: {start_date} to {end_date} vs "
            f"{_seo_prev_start} to {_seo_prev_end}. Green = improved."
        )
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

        _wc_df = _load_wc_scatter()
        if _wc_df.empty:
            st.info("No data available for scatter plot.")
        else:
            _wc_df["bubble_size"] = _wc_df["pageviews"].fillna(1).clip(lower=1)

            fig_scatter = px.scatter(
                _wc_df,
                x="word_count",
                y="avg_session_duration_s",
                size="bubble_size",
                color="bounce_rate_pct",
                hover_name="url",
                hover_data={
                    "word_count": True,
                    "organic_sessions": True,
                    "bubble_size": False,
                },
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
            st.caption(
                "Trend line shows relationship between content length and user engagement."
            )
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

# ── Content health table ──────────────────────────────────────────────────────
st.subheader("Content Health")


@st.cache_data(ttl=300)
def _load_health():
    return query_df(
        "SELECT DISTINCT ON (url) url, title, meta_description, word_count, "
        "load_time_ms, internal_links, external_links, http_status "
        "FROM raw_scrape_pages ORDER BY url, scraped_at DESC"
    )


def _health_score(row) -> str:
    issues = []
    if not row.get("meta_description"):
        issues.append("missing meta")
    if (row.get("word_count") or 0) < 300:
        issues.append("low word count")
    if (row.get("load_time_ms") or 0) > 2000:
        issues.append("slow load")
    if not issues:
        return "healthy"
    if len(issues) >= 2:
        return "issues"
    return "needs work"


with st.spinner("Loading content health..."):
    try:
        _health_df = _load_health()
        if _health_df.empty:
            st.info(
                "No scrape data available. Run gen_scrape.py --mode full to populate."
            )
        else:
            _health_df["health"] = _health_df.apply(_health_score, axis=1)
            _health_df = add_rank_column(_health_df)

            def _color_health(row):
                c = {"healthy": "#d4edda", "needs work": "#fff3cd", "issues": "#f8d7da"}
                bg = c.get(row["health"], "")
                return [f"background-color: {bg}"] * len(row)

            styled = _health_df.style.apply(_color_health, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)

            csv_bytes = _health_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download Content Health as CSV",
                data=csv_bytes,
                file_name="content_health.csv",
                mime="text/csv",
            )
            healthy = (_health_df["health"] == "healthy").sum()
            needs_work = (_health_df["health"] == "needs work").sum()
            issues = (_health_df["health"] == "issues").sum()
            st.caption(
                f"Healthy: {healthy} | Needs work: {needs_work} | Issues: {issues} "
                f"(green = healthy, yellow = needs work, red = issues)"
            )
    except Exception as exc:
        st.error(f"Could not load content health: {exc}")

st.divider()

# ── Page load time distribution ───────────────────────────────────────────────
st.subheader("Page Load Time Distribution")


@st.cache_data(ttl=300)
def _load_times():
    return query_df(
        "SELECT load_time_ms FROM raw_scrape_pages WHERE http_status = 200 AND load_time_ms IS NOT NULL"
    )


with st.spinner("Loading load time data..."):
    try:
        import plotly.graph_objects as go

        _lt_df = _load_times()
        if _lt_df.empty:
            st.info("No load time data available.")
        else:

            def _bucket(ms):
                if ms <= 500:
                    return "Fast (≤500ms)"
                if ms <= 1000:
                    return "OK (501–1000ms)"
                if ms <= 2000:
                    return "Slow (1001–2000ms)"
                return "Very Slow (>2000ms)"

            _lt_df["bucket"] = _lt_df["load_time_ms"].apply(_bucket)
            _bucket_order = [
                "Fast (≤500ms)",
                "OK (501–1000ms)",
                "Slow (1001–2000ms)",
                "Very Slow (>2000ms)",
            ]
            _bucket_colors = {
                "Fast (≤500ms)": "#28a745",
                "OK (501–1000ms)": "#ffc107",
                "Slow (1001–2000ms)": "#fd7e14",
                "Very Slow (>2000ms)": "#dc3545",
            }
            _counts = (
                _lt_df["bucket"].value_counts().reindex(_bucket_order, fill_value=0)
            )

            fig_load = go.Figure(
                go.Bar(
                    x=_counts.index.tolist(),
                    y=_counts.values.tolist(),
                    marker_color=[_bucket_colors[b] for b in _counts.index],
                )
            )
            fig_load.update_layout(
                title="Page Load Time Distribution",
                xaxis_title="Load Time Bucket",
                yaxis_title="Number of Pages",
                height=400,
                showlegend=False,
            )
            # Reference lines at 1000ms and 2000ms
            fig_load.add_vline(
                x=1.5,
                line_dash="dash",
                line_color="orange",
                annotation_text="1000ms (good threshold)",
            )
            fig_load.add_vline(
                x=2.5,
                line_dash="dash",
                line_color="red",
                annotation_text="2000ms (poor threshold)",
            )
            st.plotly_chart(fig_load, use_container_width=True)
            st.caption(
                f"Total pages: {len(_lt_df)} | Avg: {int(_lt_df['load_time_ms'].mean())}ms | "
                f"Max: {int(_lt_df['load_time_ms'].max())}ms"
            )
    except Exception as exc:
        st.error(f"Could not render load time chart: {exc}")

st.divider()

# ── Internal vs external links analysis ──────────────────────────────────────
st.subheader("Internal & External Links Analysis")


@st.cache_data(ttl=300)
def _load_links():
    return query_df(
        "SELECT DISTINCT ON (url) url, internal_links, external_links "
        "FROM raw_scrape_pages WHERE http_status = 200 ORDER BY url, scraped_at DESC"
    )


with st.spinner("Loading links data..."):
    try:
        import plotly.express as px

        _links_df = _load_links()
        if _links_df.empty:
            st.info("No links data available.")
        else:
            col_a, col_b = st.columns(2)

            # Avg internal vs external links bar
            _avg_int = round(float(_links_df["internal_links"].mean()), 1)
            _avg_ext = round(float(_links_df["external_links"].mean()), 1)
            fig_avg = px.bar(
                x=["Avg Internal Links", "Avg External Links"],
                y=[_avg_int, _avg_ext],
                color=["Avg Internal Links", "Avg External Links"],
                color_discrete_map={
                    "Avg Internal Links": "#007bff",
                    "Avg External Links": "#fd7e14",
                },
                title="Average Links per Page",
                labels={"x": "Link Type", "y": "Average Count"},
            )
            fig_avg.update_layout(showlegend=False, height=350)
            col_a.plotly_chart(fig_avg, use_container_width=True)

            # Orphan pages (zero internal links)
            _orphans = _links_df[_links_df["internal_links"] == 0]
            col_a.metric("Orphan Pages (0 internal links)", len(_orphans))
            if not _orphans.empty:
                with col_a.expander(f"View {len(_orphans)} orphan page(s)"):
                    st.dataframe(
                        _orphans[["url", "internal_links", "external_links"]],
                        hide_index=True,
                    )

            # Pages with many external links (>10)
            _heavy_ext = _links_df[_links_df["external_links"] > 10]
            fig_ext = px.histogram(
                _links_df,
                x="external_links",
                nbins=15,
                title="Distribution of External Links per Page",
                labels={"external_links": "External Links", "count": "Pages"},
                color_discrete_sequence=["#fd7e14"],
            )
            fig_ext.update_layout(height=350)
            col_b.plotly_chart(fig_ext, use_container_width=True)
            col_b.metric("Pages with >10 External Links", len(_heavy_ext))
            if not _heavy_ext.empty:
                with col_b.expander(
                    f"View {len(_heavy_ext)} page(s) with many external links"
                ):
                    st.dataframe(
                        _heavy_ext[
                            ["url", "internal_links", "external_links"]
                        ].sort_values("external_links", ascending=False),
                        hide_index=True,
                    )
    except Exception as exc:
        st.error(f"Could not load links analysis: {exc}")
