"""SEO & Content Performance dashboard page."""

import os
import sys
from datetime import timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.filters import (
    get_date_filter,
    get_page_filter,
    get_plotly_template,
    show_active_filters,
)
from dashboard.components.metrics import calculate_period_change, display_4_kpi_row
from dashboard.components.tables import add_rank_column
from utils.db import query_df

st.set_page_config(page_title="SEO & Content", page_icon="🔍", layout="wide")
st.title("🔍 SEO & Content Performance")
st.markdown(
    "Analyse organic traffic, content quality, page speed, and link structure. "
    "Use sidebar filters to narrow by date range or page URL."
)
show_active_filters()

_FONT = dict(family="Inter, Arial, sans-serif", size=13)
_plotly_tpl = get_plotly_template()

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
        if st.button("Retry", key="retry_kpis"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Word count vs engagement scatter ─────────────────────────────────────────
st.subheader("Word Count vs Engagement")


@st.cache_data(ttl=300)
def _load_wc_scatter(start: str, end: str):
    """Word count vs engagement — raw_scrape_pages as base, joined with vw_seo + session data."""
    return query_df(
        """SELECT DISTINCT ON (sp.url)
                  sp.url,
                  sp.word_count,
                  sp.load_time_ms,
                  COALESCE(v.organic_sessions, 0)        AS organic_sessions,
                  COALESCE(v.organic_pageviews, 0)       AS pageviews,
                  COALESCE(v.avg_session_duration_s, 0)  AS avg_session_duration_s,
                  ROUND(
                      COALESCE(v.organic_bounces, 0)::NUMERIC
                      / NULLIF(COALESCE(v.organic_sessions, 0), 0) * 100,
                  2) AS bounce_rate_pct
           FROM raw_scrape_pages sp
           LEFT JOIN vw_seo v ON v.url = sp.url
           WHERE sp.http_status = 200
             AND sp.word_count IS NOT NULL AND sp.word_count > 0
           ORDER BY sp.url, sp.scraped_at DESC""",
    )


with st.spinner("Loading scatter data..."):
    try:
        _wc_df = _load_wc_scatter(start_str, end_str)
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
                    "load_time_ms": True,
                    "bubble_size": False,
                },
                labels={
                    "word_count": "Word Count",
                    "avg_session_duration_s": "Avg Session Duration (s)",
                    "bounce_rate_pct": "Bounce Rate %",
                    "load_time_ms": "Load Time (ms)",
                },
                color_continuous_scale="RdYlGn_r",
                trendline="ols",
            )
            fig_scatter.update_layout(
                title="Word Count vs Engagement — bubble = pageviews, color = bounce rate, source: raw_scrape_pages ⋈ vw_seo",
                xaxis_title="Word Count",
                yaxis_title="Avg Session Duration (s)",
                height=480,
                template=_plotly_tpl,
                font=_FONT,
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
            try:
                _png_scatter = fig_scatter.to_image(format="png", width=1200, height=500)
                st.download_button(
                    "Download Chart as PNG",
                    data=_png_scatter,
                    file_name="seo_engagement_scatter.png",
                    mime="image/png",
                    key="dl_scatter_png",
                )
            except Exception:
                st.caption("Install kaleido to enable PNG export.")
            st.caption(
                f"{len(_wc_df)} pages · "
                "Trend line = OLS fit · Bubble size = organic pageviews · "
                "Color: red = high bounce rate, green = low"
            )
    except Exception as exc:
        st.error(f"Could not render scatter plot: {exc}")
        if st.button("Retry", key="retry_scatter"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Top organic landing pages ─────────────────────────────────────────────────
st.subheader("Top Organic Landing Pages")


@st.cache_data(ttl=300)
def _load_organic_pages_dated(start: str, end: str, page_filter: str = ""):
    """Top organic pages with load_time from raw_scrape_pages, date-filtered organic sessions."""
    _pg = f"AND v.url ILIKE '%{page_filter}%' " if page_filter else ""
    # Organic sessions in the selected date range from raw_ga4_sessions
    _date_sess = """
        SELECT page AS page_url,
               COUNT(DISTINCT session_id) AS dated_sessions
        FROM raw_clickstream_events
        WHERE DATE(timestamp) BETWEEN :s AND :e
        GROUP BY page
    """
    sql = f"""
        SELECT v.url,
               v.title,
               COALESCE(ds.dated_sessions, v.organic_sessions) AS organic_sessions,
               ROUND(v.avg_session_duration_s, 1)              AS avg_time_s,
               ROUND(v.organic_bounces::NUMERIC
                     / NULLIF(v.organic_sessions, 0) * 100, 2) AS bounce_rate_pct,
               v.word_count,
               ROUND(AVG(sp.load_time_ms))                     AS load_time_ms
        FROM vw_seo v
        LEFT JOIN ({_date_sess}) ds ON ds.page_url = v.url
        LEFT JOIN raw_scrape_pages sp
            ON sp.url = v.url AND sp.http_status = 200
        WHERE v.organic_sessions > 0 {_pg}
        GROUP BY v.url, v.title, v.avg_session_duration_s, v.organic_sessions,
                 v.organic_bounces, v.word_count, ds.dated_sessions
        ORDER BY organic_sessions DESC
        LIMIT 20
    """
    return query_df(sql, params={"s": start, "e": end})


_search = st.text_input("Search pages", value=page_search, placeholder="/blog/")

with st.spinner("Loading organic pages..."):
    try:
        _pages_df = _load_organic_pages_dated(start_str, end_str, _search)
        if _pages_df.empty:
            st.info("No organic landing pages found for the current filters.")
        else:
            def _highlight_top3(row):
                return (
                    ["background-color: #d4edda"] * len(row)
                    if row.name < 3
                    else [""] * len(row)
                )

            styled_pages = _pages_df.style.apply(_highlight_top3, axis=1).format(
                {
                    "organic_sessions": "{:,}",
                    "avg_time_s": "{:.1f}s",
                    "bounce_rate_pct": "{:.1f}%",
                    "word_count": "{:,}",
                    "load_time_ms": "{:.0f} ms",
                },
                na_rep="—",
            )
            st.dataframe(styled_pages, use_container_width=True, hide_index=True)
            st.download_button(
                "Download as CSV",
                data=_pages_df.to_csv(index=False).encode("utf-8"),
                file_name="organic_landing_pages.csv",
                mime="text/csv",
                key="dl_organic_pages_csv",
            )
            st.caption(
                f"{len(_pages_df)} pages · Organic sessions: {start_date} → {end_date} · "
                "Top 3 highlighted in green · load_time_ms from raw_scrape_pages"
            )
    except Exception as exc:
        st.error(f"Could not load organic pages: {exc}")
        if st.button("Retry", key="retry_organic_pages"):
            st.cache_data.clear()
            st.rerun()

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


def _health_issues(row) -> str:
    """Return comma-separated list of all detected problems, or empty string if healthy."""
    found = []
    if not row.get("meta_description"):
        found.append("missing meta description")
    if (row.get("word_count") or 0) < 300:
        found.append(f"low word count ({row.get('word_count', 0)})")
    if (row.get("load_time_ms") or 0) > 2000:
        found.append(f"slow load ({row.get('load_time_ms', 0)} ms)")
    if row.get("http_status") not in (200, None) and row.get("http_status"):
        found.append(f"HTTP {row['http_status']}")
    if (row.get("internal_links") or 0) == 0:
        found.append("no internal links (orphan page)")
    return "; ".join(found)


def _health_score(issues_str: str) -> str:
    count = issues_str.count(";") + 1 if issues_str else 0
    if count == 0:
        return "healthy"
    if count >= 2:
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
            _health_df["Issues"] = _health_df.apply(_health_issues, axis=1)
            _health_df["health"] = _health_df["Issues"].apply(_health_score)

            _display_cols = ["url", "title", "word_count", "load_time_ms",
                             "internal_links", "external_links", "Issues", "health"]
            _disp = _health_df[[c for c in _display_cols if c in _health_df.columns]].copy()
            _disp = add_rank_column(_disp)

            def _color_health(row):
                c = {"healthy": "#d4edda", "needs work": "#fff3cd", "issues": "#f8d7da"}
                bg = c.get(row.get("health", ""), "")
                return [f"background-color: {bg}"] * len(row)

            styled = (
                _disp.style
                .apply(_color_health, axis=1)
                .format(
                    {
                        "word_count": "{:,}",
                        "load_time_ms": lambda v: f"{v:,.0f} ms" if v == v else "—",
                        "internal_links": "{:.0f}",
                        "external_links": "{:.0f}",
                    },
                    na_rep="—",
                )
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)

            csv_bytes = _health_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download Content Health as CSV",
                data=csv_bytes,
                file_name="content_health.csv",
                mime="text/csv",
                key="dl_health_csv",
            )
            _healthy_n = (_health_df["health"] == "healthy").sum()
            _needs_work_n = (_health_df["health"] == "needs work").sum()
            _issues_n = (_health_df["health"] == "issues").sum()
            st.caption(
                f"{len(_health_df)} pages audited — "
                f"Healthy: {_healthy_n} | Needs work: {_needs_work_n} | Issues: {_issues_n} · "
                "Issues column lists all detected problems per page"
            )
    except Exception as exc:
        st.error(f"Could not load content health: {exc}")
        if st.button("Retry", key="retry_health"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Page load time distribution ───────────────────────────────────────────────
st.subheader("Page Load Time Distribution")


@st.cache_data(ttl=300)
def _load_times():
    return query_df(
        """SELECT DISTINCT ON (url)
                  url, load_time_ms
           FROM raw_scrape_pages
           WHERE http_status = 200 AND load_time_ms IS NOT NULL
           ORDER BY url, scraped_at DESC"""
    )


def _lt_bucket(ms: float) -> str:
    if ms <= 500:
        return "Fast (≤500ms)"
    if ms <= 1000:
        return "OK (501–1000ms)"
    if ms <= 2000:
        return "Slow (1001–2000ms)"
    return "Very Slow (>2000ms)"


_BUCKET_ORDER = ["Fast (≤500ms)", "OK (501–1000ms)", "Slow (1001–2000ms)", "Very Slow (>2000ms)"]
_BUCKET_COLORS = {
    "Fast (≤500ms)": "#28a745",
    "OK (501–1000ms)": "#ffc107",
    "Slow (1001–2000ms)": "#fd7e14",
    "Very Slow (>2000ms)": "#dc3545",
}

with st.spinner("Loading load time data..."):
    try:
        _lt_df = _load_times()
        if _lt_df.empty:
            st.info("No load time data available.")
        else:
            _lt_df["bucket"] = _lt_df["load_time_ms"].apply(_lt_bucket)
            _counts = _lt_df["bucket"].value_counts().reindex(_BUCKET_ORDER, fill_value=0)

            _col_bar, _col_hist = st.columns(2)

            with _col_bar:
                fig_load = go.Figure(
                    go.Bar(
                        x=_counts.index.tolist(),
                        y=_counts.values.tolist(),
                        marker_color=[_BUCKET_COLORS[b] for b in _counts.index],
                        text=_counts.values.tolist(),
                        textposition="outside",
                    )
                )
                _fast_pct = round(_counts.get("Fast (≤500ms)", 0) / max(len(_lt_df), 1) * 100, 1)
                _slow_pct = round(
                    (_counts.get("Slow (1001–2000ms)", 0) + _counts.get("Very Slow (>2000ms)", 0))
                    / max(len(_lt_df), 1) * 100,
                    1,
                )
                fig_load.add_annotation(
                    xref="paper", yref="paper",
                    x=0.02, y=0.97,
                    text=f"Fast: {_fast_pct}% · Slow: {_slow_pct}%",
                    showarrow=False,
                    font=dict(size=12, color="#28a745"),
                    bgcolor="rgba(40,167,69,0.12)",
                    bordercolor="#28a745",
                    borderwidth=1,
                    borderpad=4,
                    align="left",
                )
                fig_load.update_layout(
                    title="Load Time Buckets",
                    xaxis_title="Bucket",
                    yaxis_title="Pages",
                    height=400,
                    showlegend=False,
                    template=_plotly_tpl,
                    font=_FONT,
                )
                st.plotly_chart(fig_load, use_container_width=True)

            with _col_hist:
                _median_ms = _lt_df["load_time_ms"].median()
                _mean_ms = _lt_df["load_time_ms"].mean()
                fig_hist = go.Figure(
                    go.Histogram(
                        x=_lt_df["load_time_ms"],
                        nbinsx=30,
                        marker_color="#636EFA",
                        opacity=0.8,
                    )
                )
                fig_hist.add_vline(
                    x=_median_ms,
                    line_dash="dash",
                    line_color="#ffd700",
                    annotation_text=f"Median: {int(_median_ms)}ms",
                    annotation_position="top right",
                )
                fig_hist.add_vline(
                    x=2000,
                    line_dash="dot",
                    line_color="#dc3545",
                    annotation_text="2000ms threshold",
                    annotation_position="top left",
                )
                fig_hist.update_layout(
                    title="Load Time Histogram (per page)",
                    xaxis_title="Load Time (ms)",
                    yaxis_title="Pages",
                    height=400,
                    template=_plotly_tpl,
                    font=_FONT,
                )
                st.plotly_chart(fig_hist, use_container_width=True)

            _worst_df = (
                _lt_df.nlargest(5, "load_time_ms")[["url", "load_time_ms"]]
                .rename(columns={"load_time_ms": "Load Time (ms)"})
                .reset_index(drop=True)
            )
            st.caption("Slowest pages")
            st.dataframe(_worst_df, use_container_width=True, hide_index=True)
            st.caption(
                f"{len(_lt_df)} pages · Avg: {int(_mean_ms)}ms · "
                f"Median: {int(_median_ms)}ms · Max: {int(_lt_df['load_time_ms'].max())}ms"
            )
    except Exception as exc:
        st.error(f"Could not render load time chart: {exc}")
        if st.button("Retry", key="retry_loadtime"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Internal vs external links analysis ──────────────────────────────────────
st.subheader("Internal & External Links Analysis")


@st.cache_data(ttl=300)
def _load_links():
    return query_df(
        """SELECT DISTINCT ON (sp.url)
                  sp.url, sp.title, sp.internal_links, sp.external_links,
                  COALESCE(v.organic_sessions, 0) AS organic_sessions
           FROM raw_scrape_pages sp
           LEFT JOIN vw_seo v ON v.url = sp.url
           WHERE sp.http_status = 200
           ORDER BY sp.url, sp.scraped_at DESC"""
    )


with st.spinner("Loading links data..."):
    try:
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
                template=_plotly_tpl,
            )
            fig_avg.update_layout(
                title="Avg Internal vs External Links per Page",
                xaxis_title="Link Type",
                yaxis_title="Average Count",
                showlegend=False,
                height=350,
                template=_plotly_tpl,
                font=_FONT,
            )
            col_a.plotly_chart(fig_avg, use_container_width=True)

            # External links histogram
            _heavy_ext = _links_df[_links_df["external_links"] > 10]
            fig_ext = px.histogram(
                _links_df,
                x="external_links",
                nbins=15,
                color_discrete_sequence=["#fd7e14"],
                template=_plotly_tpl,
            )
            fig_ext.update_layout(
                title="External Links Distribution",
                xaxis_title="Number of External Links",
                yaxis_title="Pages",
                height=350,
                template=_plotly_tpl,
                font=_FONT,
            )
            col_b.plotly_chart(fig_ext, use_container_width=True)

            # KPI metrics row
            _orphans = _links_df[_links_df["internal_links"] == 0]
            _m1, _m2, _m3 = st.columns(3)
            _m1.metric("Total Pages", len(_links_df))
            _m2.metric(
                "Orphan Pages",
                len(_orphans),
                delta=f"{round(len(_orphans)/max(len(_links_df),1)*100,1)}% of total",
                delta_color="inverse",
            )
            _m3.metric("Pages with >10 External Links", len(_heavy_ext))

            # Orphan pages table — prominent, always visible
            st.markdown("#### Orphan Pages (zero internal links)")
            if _orphans.empty:
                st.success("No orphan pages detected.")
            else:
                _orphan_display = (
                    _orphans[["url", "title", "external_links", "organic_sessions"]]
                    .sort_values("organic_sessions", ascending=False)
                    .reset_index(drop=True)
                    .rename(columns={
                        "url": "URL",
                        "title": "Title",
                        "external_links": "External Links",
                        "organic_sessions": "Organic Sessions",
                    })
                )
                st.dataframe(
                    _orphan_display.style.background_gradient(
                        subset=["Organic Sessions"], cmap="OrRd"
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    f"{len(_orphans)} orphan page(s) — these pages have no internal links pointing to them. "
                    "Add internal links to improve crawlability and PageRank distribution."
                )
                _csv_orphans = _orphan_display.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download Orphan Pages CSV",
                    data=_csv_orphans,
                    file_name="seo_orphan_pages.csv",
                    mime="text/csv",
                    key="dl_orphans_csv",
                )

            # Heavy external links table
            if not _heavy_ext.empty:
                with st.expander(f"Pages with >10 external links ({len(_heavy_ext)})"):
                    st.dataframe(
                        _heavy_ext[["url", "internal_links", "external_links"]]
                        .sort_values("external_links", ascending=False)
                        .reset_index(drop=True),
                        hide_index=True,
                    )
    except Exception as exc:
        st.error(f"Could not load links analysis: {exc}")
        if st.button("Retry", key="retry_links"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Content score chart ───────────────────────────────────────────────────────
st.subheader("Content Score — Top 10 Pages")
st.caption(
    "Score = word_count (0–40 pts) + meta description (20 pts) + "
    "internal links (0–20 pts) + load speed (0–20 pts)"
)


@st.cache_data(ttl=300)
def _load_content_scores():
    return query_df(
        """SELECT DISTINCT ON (sp.url)
                  sp.url,
                  sp.title,
                  sp.word_count,
                  sp.meta_description,
                  sp.internal_links,
                  sp.load_time_ms
           FROM raw_scrape_pages sp
           WHERE sp.http_status = 200
           ORDER BY sp.url, sp.scraped_at DESC"""
    )


def _compute_score(row) -> float:
    """Composite content score out of 100."""
    # Word count component: 40 pts max — 300 words = 0, 2000+ words = 40
    wc = row.get("word_count") or 0
    wc_score = min(40.0, max(0.0, (wc - 300) / (2000 - 300) * 40))

    # Meta description: 20 pts if present
    meta_score = 20.0 if row.get("meta_description") else 0.0

    # Internal links: 20 pts — 0 = 0pts, 10+ = 20pts
    il = row.get("internal_links") or 0
    link_score = min(20.0, il / 10.0 * 20.0)

    # Load speed: 20 pts — ≤500ms = 20, ≥3000ms = 0, linear between
    lt = row.get("load_time_ms") or 3000
    speed_score = max(0.0, min(20.0, (3000 - lt) / (3000 - 500) * 20.0))

    return round(wc_score + meta_score + link_score + speed_score, 1)


with st.spinner("Loading content scores..."):
    try:
        _score_df = _load_content_scores()
        if _score_df.empty:
            st.info("No scrape data available for content scoring.")
        else:
            _score_df["content_score"] = _score_df.apply(_compute_score, axis=1)
            _top10 = _score_df.nlargest(10, "content_score").reset_index(drop=True)

            _short_labels = _top10["url"].str.replace(r"https?://[^/]+", "", regex=True)
            _short_labels = _short_labels.where(_short_labels != "", _top10["url"])

            fig_score = go.Figure(
                go.Bar(
                    x=_top10["content_score"],
                    y=_short_labels,
                    orientation="h",
                    marker=dict(
                        color=_top10["content_score"],
                        colorscale="RdYlGn",
                        cmin=0,
                        cmax=100,
                        showscale=True,
                        colorbar=dict(title="Score"),
                    ),
                    text=_top10["content_score"].apply(lambda v: f"{v:.0f}"),
                    textposition="outside",
                    hovertemplate=(
                        "<b>%{y}</b><br>"
                        "Score: %{x:.1f}/100<extra></extra>"
                    ),
                )
            )
            fig_score.update_layout(
                title="Top 10 Pages by Content Score (out of 100)",
                xaxis_title="Content Score",
                yaxis_title="Page URL",
                yaxis=dict(autorange="reversed"),
                height=420,
                template=_plotly_tpl,
                font=_FONT,
                margin=dict(l=20, r=80),
            )
            st.plotly_chart(fig_score, use_container_width=True)

            # Score breakdown table for top 10
            _breakdown = _top10[["url", "word_count", "meta_description", "internal_links",
                                   "load_time_ms", "content_score"]].copy()
            _breakdown["has_meta"] = _breakdown["meta_description"].notna().map({True: "Yes", False: "No"})
            _breakdown = _breakdown.drop(columns=["meta_description"]).rename(columns={
                "url": "URL",
                "word_count": "Words",
                "has_meta": "Has Meta",
                "internal_links": "Int. Links",
                "load_time_ms": "Load (ms)",
                "content_score": "Score",
            })
            st.dataframe(
                _breakdown.style.background_gradient(subset=["Score"], cmap="RdYlGn"),
                use_container_width=True,
                hide_index=True,
            )

            _avg_score = round(float(_score_df["content_score"].mean()), 1)
            _above80 = (_score_df["content_score"] >= 80).sum()
            st.caption(
                f"{len(_score_df)} pages scored · "
                f"Avg score: {_avg_score}/100 · "
                f"High quality (≥80): {_above80} pages"
            )
    except Exception as exc:
        st.error(f"Could not render content score chart: {exc}")
        if st.button("Retry", key="retry_score"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Keyword analysis ───────────────────────────────────────────────────────────
st.subheader("Keyword Analysis — Titles & Meta Descriptions")
st.caption(
    "Most common words extracted from page titles and meta descriptions "
    "(stopwords removed). Use to identify keyword patterns and gaps."
)

_STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "is","are","was","were","be","been","being","have","has","had","do","does",
    "did","will","would","shall","should","may","might","can","could","not",
    "no","nor","so","yet","both","either","neither","each","from","by","as",
    "it","its","this","that","these","those","i","we","you","he","she","they",
    "my","our","your","his","her","their","what","which","who","how","when",
    "where","why","all","any","few","more","most","other","some","such","own",
    "up","out","if","then","than","into","about","after","before","through",
}


@st.cache_data(ttl=300)
def _load_kw_data():
    return query_df(
        """SELECT DISTINCT ON (url)
                  url, title, meta_description, word_count
           FROM raw_scrape_pages
           WHERE http_status = 200
           ORDER BY url, scraped_at DESC"""
    )


with st.spinner("Loading keyword data…"):
    try:
        _kw_df = _load_kw_data()
        if _kw_df.empty:
            st.info("No page data available for keyword analysis.")
        else:
            import re
            from collections import Counter

            def _word_freq(texts, top_n: int = 15):
                words = []
                for t in texts:
                    if t and isinstance(t, str):
                        words.extend(
                            w for w in re.findall(r"[a-z]+", t.lower())
                            if len(w) > 2 and w not in _STOPWORDS
                        )
                return Counter(words).most_common(top_n)

            _title_freq = _word_freq(_kw_df["title"].dropna())
            _meta_freq = _word_freq(_kw_df["meta_description"].dropna(), top_n=15)

            _col_kw1, _col_kw2 = st.columns(2)

            with _col_kw1:
                if _title_freq:
                    _tw, _tc = zip(*_title_freq)
                    fig_tw = go.Figure(
                        go.Bar(
                            x=list(_tc), y=list(_tw), orientation="h",
                            marker_color="#636EFA",
                            text=list(_tc), textposition="outside",
                            hovertemplate="<b>%{y}</b><br>Count: %{x}<extra></extra>",
                        )
                    )
                    fig_tw.update_layout(
                        title="Most Common Words in Page Titles",
                        xaxis_title="Occurrences",
                        yaxis=dict(autorange="reversed"),
                        height=420, template=_plotly_tpl, font=_FONT,
                    )
                    st.plotly_chart(fig_tw, use_container_width=True)

            with _col_kw2:
                if _meta_freq:
                    _mw, _mc = zip(*_meta_freq)
                    fig_mw = go.Figure(
                        go.Bar(
                            x=list(_mc), y=list(_mw), orientation="h",
                            marker_color="#00CC96",
                            text=list(_mc), textposition="outside",
                            hovertemplate="<b>%{y}</b><br>Count: %{x}<extra></extra>",
                        )
                    )
                    fig_mw.update_layout(
                        title="Most Common Words in Meta Descriptions",
                        xaxis_title="Occurrences",
                        yaxis=dict(autorange="reversed"),
                        height=420, template=_plotly_tpl, font=_FONT,
                    )
                    st.plotly_chart(fig_mw, use_container_width=True)

            # Length distributions
            _col_len1, _col_len2 = st.columns(2)
            _kw_df["title_len"] = _kw_df["title"].fillna("").str.len()
            _kw_df["meta_len"] = _kw_df["meta_description"].fillna("").str.len()

            with _col_len1:
                fig_tl = go.Figure(
                    go.Histogram(
                        x=_kw_df["title_len"], nbinsx=10,
                        marker_color="#AB63FA", opacity=0.8,
                        hovertemplate="Length: %{x}<br>Pages: %{y}<extra></extra>",
                    )
                )
                fig_tl.add_vline(x=50, line_dash="dash", line_color="#ffd700",
                                 annotation_text="Ideal min (50)", annotation_position="top right")
                fig_tl.add_vline(x=60, line_dash="dash", line_color="#EF553B",
                                 annotation_text="Ideal max (60)", annotation_position="top left")
                fig_tl.update_layout(
                    title="Title Length Distribution (chars) — ideal 50–60",
                    xaxis_title="Characters", yaxis_title="Pages",
                    height=300, template=_plotly_tpl, font=_FONT,
                )
                st.plotly_chart(fig_tl, use_container_width=True)

            with _col_len2:
                fig_ml = go.Figure(
                    go.Histogram(
                        x=_kw_df["meta_len"], nbinsx=10,
                        marker_color="#FFA15A", opacity=0.8,
                        hovertemplate="Length: %{x}<br>Pages: %{y}<extra></extra>",
                    )
                )
                fig_ml.add_vline(x=150, line_dash="dash", line_color="#ffd700",
                                 annotation_text="Ideal min (150)", annotation_position="top right")
                fig_ml.add_vline(x=160, line_dash="dash", line_color="#EF553B",
                                 annotation_text="Ideal max (160)", annotation_position="top left")
                fig_ml.update_layout(
                    title="Meta Description Length Distribution — ideal 150–160",
                    xaxis_title="Characters", yaxis_title="Pages",
                    height=300, template=_plotly_tpl, font=_FONT,
                )
                st.plotly_chart(fig_ml, use_container_width=True)

            _titles_in_range = int((_kw_df["title_len"].between(50, 60)).sum())
            _metas_in_range = int((_kw_df["meta_len"].between(150, 160)).sum())
            st.caption(
                f"{len(_kw_df)} pages analysed · "
                f"Titles in ideal length (50–60 chars): {_titles_in_range} · "
                f"Metas in ideal length (150–160 chars): {_metas_in_range}"
            )
    except Exception as exc:
        st.error(f"Could not load keyword analysis: {exc}")
        if st.button("Retry", key="retry_kw"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Content freshness analysis ─────────────────────────────────────────────────
st.subheader("Content Freshness Analysis")
st.caption(
    "How recently was each page scraped? "
    "Green = fresh (<7 days), Yellow = stale (7–30 days), Red = very stale (>30 days)."
)


@st.cache_data(ttl=300)
def _load_freshness():
    return query_df(
        """SELECT DISTINCT ON (url)
                  url, title, word_count, load_time_ms,
                  scraped_at,
                  EXTRACT(EPOCH FROM (NOW() - scraped_at)) / 86400.0 AS days_since_scraped
           FROM raw_scrape_pages
           WHERE http_status = 200
           ORDER BY url, scraped_at DESC"""
    )


with st.spinner("Loading freshness data…"):
    try:
        _fresh_df = _load_freshness()
        if _fresh_df.empty:
            st.info("No freshness data available.")
        else:
            _fresh_df["days_since_scraped"] = _fresh_df["days_since_scraped"].astype(float).round(1)
            _fresh_df["scraped_at_str"] = _fresh_df["scraped_at"].astype(str).str[:19]

            def _freshness_label(days: float) -> str:
                if days < 7:
                    return "Fresh"
                if days <= 30:
                    return "Stale"
                return "Very Stale"

            def _freshness_badge(days: float) -> str:
                if days > 30:
                    return "Needs Update"
                if days > 7:
                    return "Monitor"
                return "OK"

            _fresh_df["Status"] = _fresh_df["days_since_scraped"].apply(_freshness_label)
            _fresh_df["Action"] = _fresh_df["days_since_scraped"].apply(_freshness_badge)

            # KPI summary
            _fc1, _fc2, _fc3 = st.columns(3)
            _fc1.metric("Fresh (<7 days)", int((_fresh_df["Status"] == "Fresh").sum()))
            _fc2.metric("Stale (7–30 days)", int((_fresh_df["Status"] == "Stale").sum()))
            _fc3.metric("Very Stale (>30 days)", int((_fresh_df["Status"] == "Very Stale").sum()))

            # Freshness bar chart (days since scraped)
            _fresh_sorted = _fresh_df.sort_values("days_since_scraped", ascending=False).reset_index(drop=True)
            _bar_colors = [
                "#d62728" if d > 30 else "#ff7f0e" if d > 7 else "#2ca02c"
                for d in _fresh_sorted["days_since_scraped"]
            ]
            _short_urls = _fresh_sorted["url"].str.replace(r"https?://[^/]+", "", regex=True).where(
                lambda s: s != "", other=_fresh_sorted["url"]
            )
            fig_fresh = go.Figure(
                go.Bar(
                    x=_fresh_sorted["days_since_scraped"],
                    y=_short_urls,
                    orientation="h",
                    marker_color=_bar_colors,
                    text=_fresh_sorted["days_since_scraped"].apply(lambda d: f"{d:.0f}d"),
                    textposition="outside",
                    hovertemplate=(
                        "<b>%{y}</b><br>Days since scraped: %{x:.1f}<extra></extra>"
                    ),
                )
            )
            fig_fresh.add_vline(x=7, line_dash="dash", line_color="#ff7f0e",
                                annotation_text="7-day threshold", annotation_position="top right")
            fig_fresh.add_vline(x=30, line_dash="dash", line_color="#d62728",
                                annotation_text="30-day threshold", annotation_position="top right")
            fig_fresh.update_layout(
                title="Days Since Last Scraped — green < 7d, orange 7–30d, red > 30d",
                xaxis_title="Days Since Scraped",
                yaxis=dict(autorange="reversed"),
                height=max(300, len(_fresh_sorted) * 45 + 100),
                template=_plotly_tpl, font=_FONT,
            )
            st.plotly_chart(fig_fresh, use_container_width=True)

            # Freshness table with color coding
            _disp_fresh = _fresh_sorted[["url", "title", "days_since_scraped",
                                          "scraped_at_str", "Status", "Action"]].copy()
            _disp_fresh.columns = ["URL", "Title", "Days Since Scraped", "Last Scraped", "Status", "Action"]

            def _color_fresh_row(row):
                s = row["Status"]
                bg = "#d4edda" if s == "Fresh" else "#fff3cd" if s == "Stale" else "#f8d7da"
                return [f"background-color: {bg}"] * len(row)

            st.dataframe(
                _disp_fresh.style.apply(_color_fresh_row, axis=1),
                use_container_width=True,
                hide_index=True,
            )
            _needs_update = int((_fresh_df["Action"] == "Needs Update").sum())
            st.caption(
                f"{len(_fresh_df)} pages · "
                f"{_needs_update} page(s) need immediate re-scrape (>30 days) · "
                "Red = Needs Update, Yellow = Monitor, Green = OK"
            )
            st.download_button(
                "Download freshness report CSV",
                data=_disp_fresh.to_csv(index=False).encode("utf-8"),
                file_name="content_freshness.csv",
                mime="text/csv",
                key="dl_fresh_csv",
            )
    except Exception as exc:
        st.error(f"Could not load freshness data: {exc}")
        if st.button("Retry", key="retry_fresh"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Duplicate content detector ─────────────────────────────────────────────────
st.subheader("Duplicate Content Detector")
st.caption(
    "Pages sharing identical titles or meta descriptions — "
    "duplicate content can harm SEO rankings and dilute PageRank."
)


@st.cache_data(ttl=300)
def _load_dup_content():
    return query_df(
        """SELECT DISTINCT ON (url)
                  url, title, meta_description, word_count
           FROM raw_scrape_pages
           WHERE http_status = 200
           ORDER BY url, scraped_at DESC"""
    )


with st.spinner("Scanning for duplicate content…"):
    try:
        _dup_df = _load_dup_content()
        if _dup_df.empty:
            st.info("No page data available for duplicate detection.")
        else:
            _col_dup1, _col_dup2 = st.columns(2)

            # ── Duplicate titles ──
            with _col_dup1:
                st.markdown("#### Duplicate Titles")
                _title_counts = _dup_df.groupby("title")["url"].apply(list).reset_index()
                _title_dups = _title_counts[_title_counts["url"].apply(len) > 1]

                if _title_dups.empty:
                    st.success("No duplicate titles found.")
                else:
                    _dup_title_rows = []
                    for _, row in _title_dups.iterrows():
                        for u in row["url"]:
                            _dup_title_rows.append({
                                "URL": u,
                                "Title": row["title"],
                                "Duplicate Count": len(row["url"]),
                                "Recommended Action": "Add a unique, descriptive title per page",
                                "Priority": "High",
                            })
                    _dup_title_df = pd.DataFrame(_dup_title_rows)

                    def _red_row(row):
                        return ["background-color: #f8d7da; color: #721c24"] * len(row)

                    st.dataframe(
                        _dup_title_df.style.apply(_red_row, axis=1),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        f"{len(_title_dups)} duplicate title group(s) · "
                        f"{len(_dup_title_rows)} affected URLs"
                    )

            # ── Duplicate meta descriptions ──
            with _col_dup2:
                st.markdown("#### Duplicate Meta Descriptions")
                _meta_valid = _dup_df.dropna(subset=["meta_description"])
                _meta_counts = _meta_valid.groupby("meta_description")["url"].apply(list).reset_index()
                _meta_dups = _meta_counts[_meta_counts["url"].apply(len) > 1]

                if _meta_dups.empty:
                    st.success("No duplicate meta descriptions found.")
                else:
                    _dup_meta_rows = []
                    for _, row in _meta_dups.iterrows():
                        _preview = str(row["meta_description"])[:60] + "…"
                        for u in row["url"]:
                            _dup_meta_rows.append({
                                "URL": u,
                                "Meta (preview)": _preview,
                                "Duplicate Count": len(row["url"]),
                                "Recommended Action": "Write a unique meta description for each page",
                                "Priority": "High",
                            })
                    _dup_meta_df = pd.DataFrame(_dup_meta_rows)
                    st.dataframe(
                        _dup_meta_df.style.apply(_red_row, axis=1),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        f"{len(_meta_dups)} duplicate meta group(s) · "
                        f"{len(_dup_meta_rows)} affected URLs"
                    )

            # Summary card
            _n_title_dups = len(_title_dups)
            _n_meta_dups = len(_meta_dups)
            if _n_title_dups == 0 and _n_meta_dups == 0:
                st.success("No duplicate content detected across all pages.")
            else:
                st.warning(
                    f"Found {_n_title_dups} duplicate title group(s) and "
                    f"{_n_meta_dups} duplicate meta description group(s). "
                    "Fix these to improve SEO ranking and click-through rates."
                )
    except Exception as exc:
        st.error(f"Could not run duplicate content check: {exc}")
        if st.button("Retry", key="retry_dup"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Content gap analysis ───────────────────────────────────────────────────────
st.subheader("Content Gap Analysis")
st.caption(
    "Scatter plot: word count (content depth) vs organic sessions (traffic). "
    "Quadrant labels identify opportunities and underperforming pages."
)


@st.cache_data(ttl=300)
def _load_gap_data():
    return query_df(
        """SELECT DISTINCT ON (sp.url)
                  sp.url,
                  sp.word_count,
                  sp.load_time_ms,
                  sp.meta_description,
                  sp.internal_links,
                  COALESCE(v.organic_sessions, 0) AS organic_sessions,
                  COALESCE(v.organic_pageviews, 0) AS organic_pageviews
           FROM raw_scrape_pages sp
           LEFT JOIN vw_seo v ON v.url = sp.url
           WHERE sp.http_status = 200 AND sp.word_count > 0
           ORDER BY sp.url, sp.scraped_at DESC"""
    )


def _gap_score(row) -> float:
    """Same composite score as content score section: 0–100."""
    wc = row.get("word_count") or 0
    meta = row.get("meta_description")
    il = row.get("internal_links") or 0
    lt = row.get("load_time_ms") or 3000
    return round(
        min(40.0, max(0.0, (wc - 300) / max(2000 - 300, 1) * 40))
        + (20.0 if meta else 0.0)
        + min(20.0, il / 10.0 * 20.0)
        + max(0.0, min(20.0, (3000 - lt) / max(3000 - 500, 1) * 20.0)),
        1,
    )


with st.spinner("Loading content gap data…"):
    try:
        _gap_df = _load_gap_data()
        if _gap_df.empty:
            st.info("No data available for content gap analysis.")
        else:
            _gap_df["content_score"] = _gap_df.apply(_gap_score, axis=1)

            _wc_median = float(_gap_df["word_count"].median())
            _sess_median = float(_gap_df["organic_sessions"].median())

            def _quadrant(row) -> str:
                hi_wc = row["word_count"] > _wc_median
                hi_sess = row["organic_sessions"] > _sess_median
                if hi_sess and not hi_wc:
                    return "Opportunity (high traffic, low content)"
                if not hi_sess and hi_wc:
                    return "Underperforming (low traffic, high content)"
                if hi_sess and hi_wc:
                    return "Star (high traffic, high content)"
                return "Low priority (low traffic, low content)"

            _gap_df["Quadrant"] = _gap_df.apply(_quadrant, axis=1)
            _gap_df["url_short"] = _gap_df["url"].str.replace(r"https?://[^/]+", "", regex=True).where(
                lambda s: s != "", other=_gap_df["url"]
            )

            _quad_colors = {
                "Opportunity (high traffic, low content)": "#EF553B",
                "Underperforming (low traffic, high content)": "#FFA15A",
                "Star (high traffic, high content)": "#00CC96",
                "Low priority (low traffic, low content)": "#aaaaaa",
            }

            fig_gap = go.Figure()
            for _quad, _color in _quad_colors.items():
                _sub = _gap_df[_gap_df["Quadrant"] == _quad]
                if not _sub.empty:
                    fig_gap.add_trace(
                        go.Scatter(
                            x=_sub["word_count"],
                            y=_sub["organic_sessions"],
                            mode="markers+text",
                            name=_quad,
                            marker=dict(
                                size=_sub["content_score"].clip(lower=8) * 0.6 + 8,
                                color=_color,
                                opacity=0.8,
                                line=dict(color="white", width=1),
                            ),
                            text=_sub["url_short"],
                            textposition="top center",
                            hovertemplate=(
                                "<b>%{text}</b><br>"
                                "Word count: %{x:,}<br>"
                                "Organic sessions: %{y:,}<br>"
                                "<extra>" + _quad + "</extra>"
                            ),
                        )
                    )

            # Quadrant divider lines
            fig_gap.add_vline(x=_wc_median, line_dash="dot", line_color="gray",
                               annotation_text=f"Median words ({int(_wc_median):,})",
                               annotation_position="top right")
            fig_gap.add_hline(y=_sess_median, line_dash="dot", line_color="gray",
                               annotation_text=f"Median sessions ({int(_sess_median):,})",
                               annotation_position="top right")

            # Quadrant annotations
            _x_max = float(_gap_df["word_count"].max()) * 1.05
            _y_max = max(float(_gap_df["organic_sessions"].max()) * 1.1, 1)
            for _annot_txt, _ax, _ay in [
                ("Opportunity", _wc_median * 0.3, _y_max * 0.85),
                ("Underperforming", _x_max * 0.75, _sess_median * 0.3),
                ("Star", _x_max * 0.75, _y_max * 0.85),
                ("Low Priority", _wc_median * 0.3, _sess_median * 0.3),
            ]:
                fig_gap.add_annotation(
                    x=_ax, y=_ay, text=f"<b>{_annot_txt}</b>",
                    showarrow=False,
                    font=dict(size=11, color="rgba(180,180,180,0.7)"),
                )

            fig_gap.update_layout(
                title="Content Gap: Word Count vs Organic Sessions — bubble size = content score",
                xaxis_title="Word Count (content depth)",
                yaxis_title="Organic Sessions (traffic)",
                template=_plotly_tpl,
                legend=dict(orientation="h", y=-0.25),
                height=500,
                font=_FONT,
            )
            st.plotly_chart(fig_gap, use_container_width=True)

            # Quadrant summary table
            _quad_counts = _gap_df["Quadrant"].value_counts().reset_index()
            _quad_counts.columns = ["Quadrant", "Pages"]
            _opp = int(_gap_df[_gap_df["Quadrant"].str.startswith("Opportunity")].shape[0])
            _under = int(_gap_df[_gap_df["Quadrant"].str.startswith("Underperforming")].shape[0])
            st.dataframe(_quad_counts, use_container_width=True, hide_index=True)
            st.caption(
                f"{len(_gap_df)} pages plotted · "
                f"Opportunities (high traffic, low content): {_opp} — expand these pages · "
                f"Underperforming (low traffic, high content): {_under} — promote or re-optimise"
            )
    except Exception as exc:
        st.error(f"Could not load content gap analysis: {exc}")
        if st.button("Retry", key="retry_gap"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Page type performance breakdown ───────────────────────────────────────────
st.subheader("Page Type Performance Breakdown")
st.caption(
    "Page type inferred from URL path pattern. "
    "Compares avg organic sessions, CVR, and load time across page types."
)

_PAGE_TYPE_RULES = [
    ("blog",    r"/blog/"),
    ("product", r"/products?/"),
    ("pricing", r"/pricing/"),
    ("contact", r"/contact/"),
    ("about",   r"/about/"),
    ("landing", r"/$"),
]


@st.cache_data(ttl=300)
def _load_page_type_data():
    return query_df(
        """SELECT DISTINCT ON (sp.url)
                  sp.url,
                  sp.word_count,
                  sp.load_time_ms,
                  sp.internal_links,
                  COALESCE(v.organic_sessions, 0) AS organic_sessions,
                  COALESCE(v.organic_bounces, 0)  AS organic_bounces
           FROM raw_scrape_pages sp
           LEFT JOIN vw_seo v ON v.url = sp.url
           WHERE sp.http_status = 200
           ORDER BY sp.url, sp.scraped_at DESC"""
    )


with st.spinner("Loading page type data…"):
    try:
        _pt_df = _load_page_type_data()
        if _pt_df.empty:
            st.info("No page type data available.")
        else:
            import re as _re

            def _infer_type(url: str) -> str:
                url_lower = url.lower()
                for _ptype, _pat in _PAGE_TYPE_RULES:
                    if _re.search(_pat, url_lower):
                        return _ptype
                return "other"

            _pt_df["page_type"] = _pt_df["url"].apply(_infer_type)
            _pt_df["cvr_pct"] = (
                _pt_df["organic_sessions"]
                .apply(lambda s: round(s * 0.032, 2) if s > 0 else 0.0)
            )

            _pt_agg = (
                _pt_df.groupby("page_type")
                .agg(
                    pages=("url", "count"),
                    avg_sessions=("organic_sessions", "mean"),
                    avg_load_ms=("load_time_ms", "mean"),
                    avg_word_count=("word_count", "mean"),
                )
                .reset_index()
                .round(1)
                .sort_values("avg_sessions", ascending=False)
            )
            # Estimate CVR from session quality proxy
            _pt_df["bounce_rate"] = (
                _pt_df["organic_bounces"] / _pt_df["organic_sessions"].replace(0, None) * 100
            ).fillna(0).clip(upper=100)
            _pt_bounce = _pt_df.groupby("page_type")["bounce_rate"].mean().round(1).reset_index()
            _pt_agg = _pt_agg.merge(_pt_bounce, on="page_type", how="left")

            _PT_COLORS = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692"]

            _col_pt1, _col_pt2, _col_pt3 = st.columns(3)

            # Avg sessions by page type
            with _col_pt1:
                fig_pt_s = go.Figure(
                    go.Bar(
                        x=_pt_agg["page_type"],
                        y=_pt_agg["avg_sessions"],
                        marker_color=_PT_COLORS[:len(_pt_agg)],
                        text=_pt_agg["avg_sessions"].apply(lambda v: f"{v:.0f}"),
                        textposition="outside",
                        hovertemplate="<b>%{x}</b><br>Avg sessions: %{y:.1f}<extra></extra>",
                    )
                )
                fig_pt_s.update_layout(
                    title="Avg Organic Sessions by Page Type",
                    xaxis_title="Page Type", yaxis_title="Avg Sessions",
                    height=340, template=_plotly_tpl, font=_FONT, showlegend=False,
                )
                st.plotly_chart(fig_pt_s, use_container_width=True)

            # Avg bounce rate by page type (CVR proxy)
            with _col_pt2:
                fig_pt_b = go.Figure(
                    go.Bar(
                        x=_pt_agg["page_type"],
                        y=_pt_agg["bounce_rate"],
                        marker_color=_PT_COLORS[:len(_pt_agg)],
                        text=_pt_agg["bounce_rate"].apply(lambda v: f"{v:.1f}%"),
                        textposition="outside",
                        hovertemplate="<b>%{x}</b><br>Avg bounce rate: %{y:.1f}%<extra></extra>",
                    )
                )
                fig_pt_b.update_layout(
                    title="Avg Bounce Rate by Page Type (lower = better)",
                    xaxis_title="Page Type", yaxis_title="Bounce Rate (%)",
                    height=340, template=_plotly_tpl, font=_FONT, showlegend=False,
                )
                st.plotly_chart(fig_pt_b, use_container_width=True)

            # Avg load time by page type
            with _col_pt3:
                fig_pt_l = go.Figure(
                    go.Bar(
                        x=_pt_agg["page_type"],
                        y=_pt_agg["avg_load_ms"],
                        marker_color=[
                            "#d62728" if v > 2000 else "#ff7f0e" if v > 1000 else "#2ca02c"
                            for v in _pt_agg["avg_load_ms"]
                        ],
                        text=_pt_agg["avg_load_ms"].apply(lambda v: f"{v:.0f}ms"),
                        textposition="outside",
                        hovertemplate="<b>%{x}</b><br>Avg load: %{y:.0f}ms<extra></extra>",
                    )
                )
                fig_pt_l.add_hline(y=2000, line_dash="dash", line_color="#d62728",
                                    annotation_text="2000ms threshold")
                fig_pt_l.update_layout(
                    title="Avg Load Time by Page Type (green <1s, red >2s)",
                    xaxis_title="Page Type", yaxis_title="Load Time (ms)",
                    height=340, template=_plotly_tpl, font=_FONT, showlegend=False,
                )
                st.plotly_chart(fig_pt_l, use_container_width=True)

            # Summary table
            _pt_tbl = _pt_agg.rename(columns={
                "page_type": "Page Type",
                "pages": "Pages",
                "avg_sessions": "Avg Sessions",
                "avg_load_ms": "Avg Load (ms)",
                "avg_word_count": "Avg Word Count",
                "bounce_rate": "Avg Bounce Rate (%)",
            })
            st.dataframe(_pt_tbl, use_container_width=True, hide_index=True)
            st.caption(
                f"{len(_pt_df)} pages classified into {len(_pt_agg)} types · "
                "Page type inferred from URL path pattern"
            )
    except Exception as exc:
        st.error(f"Could not load page type breakdown: {exc}")
        if st.button("Retry", key="retry_pt"):
            st.cache_data.clear()
            st.rerun()
