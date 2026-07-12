"""User Behavior & Funnels — loads from vw_behavior, vw_top_pages,
vw_scroll_depth, and vw_engagement_events."""

import os
import sys

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.charts import bar_chart, line_chart
from dashboard.components.filters import get_date_filter, get_page_filter
from dashboard.components.metrics import (
    display_kpi_row,
    format_duration,
    format_number,
    format_percentage,
)
from utils.db import query_df
from utils.query_runner import run_view

st.set_page_config(page_title="User Behavior & Funnels", page_icon="🖱️", layout="wide")
st.title("🖱️ User Behavior & Funnels")


# ── Cached loaders (TTL = 5 minutes) ─────────────────────────────────────────
@st.cache_data(ttl=300)
def _load_behavior():
    return run_view("vw_behavior")


@st.cache_data(ttl=300)
def _load_top_pages():
    return run_view("vw_top_pages")


@st.cache_data(ttl=300)
def _load_scroll():
    return run_view("vw_scroll_depth")


@st.cache_data(ttl=300)
def _load_engagement():
    return run_view("vw_engagement_events")


@st.cache_data(ttl=300)
def _load_avg_time():
    return query_df(
        "SELECT ROUND(AVG(session_duration_s)::numeric, 1) AS avg_s FROM raw_ga4_sessions"
    )


@st.cache_data(ttl=300)
def _load_funnel():
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


@st.cache_data(ttl=300)
def _load_duration():
    return query_df("""
SELECT
    COUNT(CASE WHEN session_duration_s < 30                                   THEN 1 END) AS "0–30s",
    COUNT(CASE WHEN session_duration_s >= 30  AND session_duration_s < 120    THEN 1 END) AS "30s–2m",
    COUNT(CASE WHEN session_duration_s >= 120 AND session_duration_s < 300    THEN 1 END) AS "2m–5m",
    COUNT(CASE WHEN session_duration_s >= 300 AND session_duration_s < 600    THEN 1 END) AS "5m–10m",
    COUNT(CASE WHEN session_duration_s >= 600                                 THEN 1 END) AS "10m+"
FROM raw_ga4_sessions WHERE session_duration_s IS NOT NULL
""")


@st.cache_data(ttl=300)
def _load_heatmap():
    return query_df("""
SELECT EXTRACT(DOW FROM log_time)::int AS dow,
       EXTRACT(HOUR FROM log_time)::int AS hour_of_day,
       COUNT(*) AS total_requests
FROM raw_server_logs GROUP BY 1, 2 ORDER BY 1, 2
""")


@st.cache_data(ttl=300)
def _load_retention():
    return query_df("""
        SELECT
            DATE_TRUNC('week', session_date)::DATE AS week_start,
            SUM(sessions)  AS weekly_sessions,
            SUM(new_users) AS new_users,
            SUM(sessions) - SUM(new_users) AS returning_users,
            ROUND((SUM(sessions) - SUM(new_users))::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS retention_rate_pct
        FROM raw_ga4_sessions
        GROUP BY week_start
        ORDER BY week_start
    """)


@st.cache_data(ttl=300)
def _load_session_quality():
    return query_df("""
        WITH quality AS (
            SELECT
                channel_grouping,
                COUNT(*) AS total_sessions,
                COUNT(CASE WHEN session_duration_s > 180 AND NOT bounce THEN 1 END) AS high_quality,
                COUNT(CASE WHEN session_duration_s < 30 OR bounce THEN 1 END) AS low_quality
            FROM raw_ga4_sessions
            GROUP BY channel_grouping
        )
        SELECT channel_grouping, total_sessions, high_quality, low_quality,
               ROUND(high_quality::NUMERIC / NULLIF(total_sessions, 0) * 100, 2) AS high_quality_pct,
               ROUND(low_quality::NUMERIC  / NULLIF(total_sessions, 0) * 100, 2) AS low_quality_pct
        FROM quality ORDER BY high_quality_pct DESC
    """)


@st.cache_data(ttl=300)
def _load_quality_heatmap():
    return query_df("""
        SELECT EXTRACT(DOW FROM session_date)::INT AS dow,
               EXTRACT(HOUR FROM (session_date + interval '12 hours'))::INT AS hour_of_day,
               COUNT(CASE WHEN session_duration_s > 180 AND NOT bounce THEN 1 END) AS high_quality
        FROM raw_ga4_sessions
        GROUP BY dow, hour_of_day
        ORDER BY dow, hour_of_day
    """)


@st.cache_data(ttl=300)
def _load_dau_mau():
    return query_df("""
        WITH dau AS (
            SELECT session_date, SUM(sessions) AS daily_s FROM raw_ga4_sessions GROUP BY session_date
        ),
        mau AS (
            SELECT DATE_TRUNC('month', session_date)::DATE AS mo,
                   SUM(sessions) ms, COUNT(DISTINCT session_date) active_days
            FROM raw_ga4_sessions GROUP BY mo
        )
        SELECT m.mo AS month_start, m.ms AS monthly_sessions, m.active_days,
               ROUND(m.ms::NUMERIC / NULLIF(m.active_days, 0), 1) AS avg_dau
        FROM mau m ORDER BY m.mo
    """)


# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    start_date, end_date = get_date_filter()
    page_search = get_page_filter()
    st.divider()
    if st.button("Clear data cache"):
        st.cache_data.clear()
        st.success("Cache cleared — reloading…")
    st.caption("Cache TTL: 5 min")
    if page_search:
        st.success("Page filter applied")

# ── Load data ─────────────────────────────────────────────────────────────────
try:
    with st.spinner("Loading behavior data from PostgreSQL…"):
        df_behavior = _load_behavior()
        df_top_pages = _load_top_pages()
        df_scroll = _load_scroll()
        df_engagement = _load_engagement()
except Exception as exc:
    st.error(
        f"Could not load behavior data from the database. "
        f"Check your PostgreSQL connection and try again.\n\n**Error:** {exc}"
    )
    st.stop()

# Apply page URL filter
if page_search:
    df_behavior = df_behavior[
        df_behavior["page"].str.contains(page_search, case=False, na=False)
    ].reset_index(drop=True)
    df_top_pages = df_top_pages[
        df_top_pages["url"].str.contains(page_search, case=False, na=False)
    ].reset_index(drop=True)
    df_scroll = df_scroll[
        df_scroll["page_url"].str.contains(page_search, case=False, na=False)
    ].reset_index(drop=True)
    df_engagement = df_engagement[
        df_engagement["page_url"].str.contains(page_search, case=False, na=False)
    ].reset_index(drop=True)

with st.expander("Debug: data shapes", expanded=False):
    st.write(
        {
            "vw_behavior": df_behavior.shape,
            "vw_top_pages": df_top_pages.shape,
            "vw_scroll_depth": df_scroll.shape,
            "vw_engagement_events": df_engagement.shape,
        }
    )

# ── KPI cards ─────────────────────────────────────────────────────────────────
total_pageviews = (
    int(df_top_pages["total_requests"].sum()) if not df_top_pages.empty else 0
)

_time_row = _load_avg_time()
avg_time_s = float(_time_row["avg_s"].iloc[0]) if not _time_row.empty else 0.0

avg_scroll = (
    float(df_scroll["avg_scroll_depth_pct"].mean()) if not df_scroll.empty else 0.0
)

total_events = (
    int(df_engagement["total_events"].sum()) if not df_engagement.empty else 0
)

display_kpi_row(
    [
        {"title": "Total Page Views", "value": format_number(total_pageviews)},
        {"title": "Avg Time on Page", "value": format_duration(avg_time_s)},
        {"title": "Avg Scroll Depth", "value": format_percentage(avg_scroll)},
        {"title": "Total Events Tracked", "value": format_number(total_events)},
    ]
)

st.divider()

# ── Top pages table ────────────────────────────────────────────────────────────
st.subheader("Top Pages")
search = st.text_input("Filter by URL", placeholder="/blog/", key="top_pages_search")

if not df_top_pages.empty:
    df_tp = df_top_pages[
        ["url", "total_requests", "avg_response_time_ms", "error_rate_pct"]
    ].copy()
    df_tp = df_tp.sort_values("total_requests", ascending=False)
    if search:
        df_tp = df_tp[df_tp["url"].str.contains(search, case=False, na=False)]

    def _highlight_slow(row):
        bg = "background-color: #ffd6d6" if row["avg_response_time_ms"] > 1000 else ""
        return [bg] * len(row)

    st.dataframe(
        df_tp.style.apply(_highlight_slow, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Rows highlighted in red have avg response time > 1,000 ms")
else:
    st.info("No page data available.")

st.divider()

# ── Conversion funnel ─────────────────────────────────────────────────────────
st.subheader("Conversion Funnel")

df_funnel = _load_funnel()

if not df_funnel.empty:
    stages = ["Homepage", "Product Page", "Add to Cart", "Checkout", "Purchase"]
    values = [
        int(df_funnel["homepage"].iloc[0]),
        int(df_funnel["product_page"].iloc[0]),
        int(df_funnel["add_to_cart"].iloc[0]),
        int(df_funnel["checkout"].iloc[0]),
        int(df_funnel["purchase"].iloc[0]),
    ]
    fig_funnel = go.Figure(
        go.Funnel(
            y=stages,
            x=values,
            textinfo="value+percent initial",
            marker_color=["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"],
        )
    )
    fig_funnel.update_layout(
        title="Homepage → Purchase Conversion Funnel",
        template="plotly_white",
    )
    st.plotly_chart(fig_funnel, use_container_width=True)
else:
    st.info("No funnel data available.")

st.divider()

# ── Scroll depth histogram ────────────────────────────────────────────────────
st.subheader("Scroll Depth Distribution")
if not df_scroll.empty:
    import pandas as pd

    buckets = {
        "0–25%": int(df_scroll["bucket_0_25"].sum()),
        "25–50%": int(df_scroll["bucket_25_50"].sum()),
        "50–75%": int(df_scroll["bucket_50_75"].sum()),
        "75–100%": int(df_scroll["bucket_75_100"].sum()),
    }
    df_buckets = pd.DataFrame(
        {
            "Bucket": list(buckets.keys()),
            "Sessions": list(buckets.values()),
            "Color": ["#d62728", "#ff7f0e", "#ffbb78", "#2ca02c"],
        }
    )
    fig_scroll = go.Figure(
        go.Bar(
            x=df_buckets["Bucket"],
            y=df_buckets["Sessions"],
            marker_color=df_buckets["Color"].tolist(),
            text=df_buckets["Sessions"],
            textposition="outside",
        )
    )
    fig_scroll.update_layout(
        title="Scroll Depth Buckets (all pages)",
        xaxis_title="Scroll Depth",
        yaxis_title="Event Count",
        template="plotly_white",
    )
    st.plotly_chart(fig_scroll, use_container_width=True)
else:
    st.info("No scroll depth data available.")

st.divider()

# ── Engagement events breakdown ───────────────────────────────────────────────
st.subheader("Engagement Events Breakdown")
if not df_engagement.empty:
    import pandas as pd

    ev_totals = {
        "Click": int(df_engagement["click_events"].sum()),
        "Scroll": int(df_engagement["scroll_events"].sum()),
        "Pageview": int(df_engagement["pageview_events"].sum()),
        "Form Submit": int(df_engagement["form_submit_events"].sum()),
    }
    grand = sum(ev_totals.values()) or 1
    df_ev = pd.DataFrame(
        {
            "Event Type": list(ev_totals.keys()),
            "Count": list(ev_totals.values()),
            "Pct": [f"{v / grand * 100:.1f}%" for v in ev_totals.values()],
            "Color": ["#636EFA", "#EF553B", "#00CC96", "#AB63FA"],
        }
    )
    fig_ev = go.Figure(
        go.Bar(
            x=df_ev["Event Type"],
            y=df_ev["Count"],
            marker_color=df_ev["Color"].tolist(),
            text=df_ev["Pct"],
            textposition="outside",
        )
    )
    fig_ev.update_layout(
        title="Events by Type (all pages)",
        xaxis_title="Event Type",
        yaxis_title="Count",
        template="plotly_white",
    )
    st.plotly_chart(fig_ev, use_container_width=True)
else:
    st.info("No engagement event data available.")

st.divider()

# ── Session duration distribution ─────────────────────────────────────────────
st.subheader("Session Duration Distribution")
df_dur = _load_duration()
if not df_dur.empty:
    import pandas as pd

    dur_labels = ["0–30s", "30s–2m", "2m–5m", "5m–10m", "10m+"]
    dur_values = [int(df_dur[col].iloc[0]) for col in dur_labels]
    df_dur_plot = pd.DataFrame({"Bucket": dur_labels, "Sessions": dur_values})
    fig_dur = bar_chart(
        df_dur_plot,
        x="Bucket",
        y="Sessions",
        title="Session Duration Distribution",
        labels={"Bucket": "Duration", "Sessions": "Sessions"},
    )
    st.plotly_chart(fig_dur, use_container_width=True)
else:
    st.info("No session duration data available.")

st.divider()

# ── Top pages by engagement score ─────────────────────────────────────────────
st.subheader("Top Pages by Engagement Score")
if not df_behavior.empty:
    import pandas as pd

    df_eng = df_behavior.copy()
    # score = (scroll_depth * 0.4) + (events_count * 0.3) + (time_on_page * 0.3)
    # Normalise each component to 0-1 range before weighting
    max_scroll = df_eng["avg_scroll_depth_pct"].max() or 1
    max_events = df_eng["total_events"].max() or 1
    max_resp = df_eng["avg_response_ms"].max() or 1
    df_eng["score"] = (
        (df_eng["avg_scroll_depth_pct"].fillna(0) / max_scroll) * 0.4
        + (df_eng["total_events"] / max_events) * 0.3
        + (1 - df_eng["avg_response_ms"] / max_resp) * 0.3  # faster = better
    ).round(4)
    df_top10 = df_eng.nlargest(10, "score")[["page", "score"]].reset_index(drop=True)
    df_top10_sorted = df_top10.sort_values("score", ascending=True)
    fig_eng = go.Figure(
        go.Bar(
            x=df_top10_sorted["score"],
            y=df_top10_sorted["page"],
            orientation="h",
            marker=dict(
                color=df_top10_sorted["score"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="Score"),
            ),
        )
    )
    fig_eng.update_layout(
        title="Top 10 Pages by Engagement Score",
        xaxis_title="Engagement Score",
        yaxis_title="Page",
        template="plotly_white",
    )
    st.plotly_chart(fig_eng, use_container_width=True)
else:
    st.info("No behavior data available.")

st.divider()

# ── Page views over time ───────────────────────────────────────────────────────
st.subheader("Page Views Over Time")
pv_url = st.text_input(
    "Filter by page URL (optional)", placeholder="/blog/", key="pv_url_filter"
)
_pv_where = "AND url ILIKE :url_pat" if pv_url else ""
_pv_params = {"url_pat": f"%{pv_url}%"} if pv_url else {}
_pv_sql = f"""
SELECT DATE(log_time) AS log_date, COUNT(*) AS total_requests
FROM raw_server_logs
WHERE 1=1 {_pv_where}
GROUP BY DATE(log_time)
ORDER BY log_date
"""
df_pv = query_df(_pv_sql, _pv_params)
if not df_pv.empty:
    fig_pv = line_chart(
        df_pv,
        x="log_date",
        y="total_requests",
        title="Daily Page Requests" + (f" — {pv_url}" if pv_url else ""),
        labels={"log_date": "Date", "total_requests": "Requests"},
    )
    st.plotly_chart(fig_pv, use_container_width=True)
else:
    st.info("No page view data for the selected URL.")

st.divider()

# ── Retention Analysis ────────────────────────────────────────────────────────
st.subheader("Retention Analysis")

import pandas as pd

df_dau_mau = _load_dau_mau()
df_retention = _load_retention()

# KPI cards: DAU, WAU, MAU, stickiness
if not df_retention.empty:
    last_week_row = df_retention.iloc[-1]
    dau_approx = int(last_week_row.get("weekly_sessions", 0) / 7 or 0)
    wau = int(last_week_row.get("weekly_sessions", 0) or 0)
    mau = int(df_dau_mau["monthly_sessions"].iloc[-1]) if not df_dau_mau.empty else 0
    stickiness = round(dau_approx / mau * 100, 1) if mau else 0
    ret_rate = float(last_week_row.get("retention_rate_pct", 0) or 0)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("DAU (last week avg)", f"{dau_approx:,}")
    with k2:
        st.metric("WAU (last week)", f"{wau:,}")
    with k3:
        st.metric("MAU (last month)", f"{mau:,}")
    with k4:
        st.metric("Stickiness (DAU/MAU)", f"{stickiness}%")

    # Retention trend chart
    fig_ret = go.Figure()
    fig_ret.add_trace(
        go.Scatter(
            x=df_retention["week_start"].astype(str),
            y=df_retention["retention_rate_pct"],
            mode="lines+markers",
            name="Retention Rate %",
            line=dict(color="#00CC96", width=2),
        )
    )
    fig_ret.add_trace(
        go.Bar(
            x=df_retention["week_start"].astype(str),
            y=df_retention["weekly_sessions"],
            name="Weekly Sessions",
            yaxis="y2",
            opacity=0.3,
            marker_color="#636EFA",
        )
    )
    fig_ret.update_layout(
        title="Weekly Retention Rate & Session Volume",
        xaxis_title="Week",
        yaxis=dict(title="Retention Rate %", range=[0, 100]),
        yaxis2=dict(title="Sessions", overlaying="y", side="right"),
        template="plotly_white",
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig_ret, use_container_width=True)

    # Re-engagement rate by channel
    df_reeng = query_df("""
        SELECT channel_grouping,
               ROUND((SUM(sessions) - SUM(new_users))::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS re_engagement_pct
        FROM raw_ga4_sessions
        GROUP BY channel_grouping ORDER BY re_engagement_pct DESC
    """)
    if not df_reeng.empty:
        fig_re = go.Figure(
            go.Bar(
                x=df_reeng["channel_grouping"],
                y=df_reeng["re_engagement_pct"],
                marker_color="#AB63FA",
                text=df_reeng["re_engagement_pct"].apply(lambda v: f"{v}%"),
                textposition="outside",
            )
        )
        fig_re.update_layout(
            title="Re-engagement Rate by Channel (Returning Users %)",
            xaxis_title="Channel",
            yaxis_title="Re-engagement %",
            template="plotly_white",
        )
        st.plotly_chart(fig_re, use_container_width=True)
else:
    st.info("No retention data available.")

st.divider()

# ── Session Quality ───────────────────────────────────────────────────────────
st.subheader("Session Quality")

df_sq = _load_session_quality()

if not df_sq.empty:
    total_all = int(df_sq["total_sessions"].sum())
    high_all = int(df_sq["high_quality"].sum())
    low_all = int(df_sq["low_quality"].sum())
    mid_all = total_all - high_all - low_all

    sq1, sq2, sq3 = st.columns(3)
    with sq1:
        st.metric(
            "High Quality Sessions",
            f"{high_all:,}",
            delta=(
                f"{round(high_all / total_all * 100, 1)}% of total"
                if total_all
                else None
            ),
        )
    with sq2:
        st.metric("Medium Quality Sessions", f"{mid_all:,}")
    with sq3:
        st.metric(
            "Low Quality Sessions",
            f"{low_all:,}",
            delta=(
                f"-{round(low_all / total_all * 100, 1)}% bounce/quick-exit"
                if total_all
                else None
            ),
            delta_color="inverse",
        )

    # High / low quality pie
    pie_col, bar_col = st.columns(2)
    with pie_col:
        fig_pie = go.Figure(
            go.Pie(
                labels=["High Quality", "Medium Quality", "Low Quality"],
                values=[high_all, mid_all, low_all],
                marker_colors=["#2ca02c", "#ffbb78", "#d62728"],
                hole=0.35,
            )
        )
        fig_pie.update_layout(
            title="Session Quality Distribution", template="plotly_white"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with bar_col:
        fig_bar = go.Figure()
        fig_bar.add_trace(
            go.Bar(
                name="High Quality %",
                x=df_sq["channel_grouping"],
                y=df_sq["high_quality_pct"],
                marker_color="#2ca02c",
            )
        )
        fig_bar.add_trace(
            go.Bar(
                name="Low Quality %",
                x=df_sq["channel_grouping"],
                y=df_sq["low_quality_pct"],
                marker_color="#d62728",
            )
        )
        fig_bar.update_layout(
            barmode="group",
            title="Session Quality by Channel",
            xaxis_title="Channel",
            yaxis_title="% of Sessions",
            template="plotly_white",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Best time heatmap — high quality sessions by day-of-week
    df_qheat = _load_quality_heatmap()
    if not df_qheat.empty:
        _day_map2 = {
            0: "Sun",
            1: "Mon",
            2: "Tue",
            3: "Wed",
            4: "Thu",
            5: "Fri",
            6: "Sat",
        }
        df_qheat["day_name"] = df_qheat["dow"].map(_day_map2)
        pivot_q = df_qheat.pivot_table(
            index="day_name",
            columns="hour_of_day",
            values="high_quality",
            fill_value=0,
        )
        day_order2 = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        pivot_q = pivot_q.reindex([d for d in day_order2 if d in pivot_q.index])
        fig_qheat = go.Figure(
            go.Heatmap(
                z=pivot_q.values.tolist(),
                x=[str(h) for h in pivot_q.columns.tolist()],
                y=pivot_q.index.tolist(),
                colorscale="Greens",
                hoverongaps=False,
                colorbar=dict(title="High Quality"),
            )
        )
        fig_qheat.update_layout(
            title="Best Time for High Quality Sessions (Day × Hour)",
            xaxis_title="Hour of Day",
            yaxis_title="Day of Week",
            template="plotly_white",
        )
        st.plotly_chart(fig_qheat, use_container_width=True)
else:
    st.info("No session quality data available.")

st.divider()

# ── Traffic heatmap by day and hour ───────────────────────────────────────────
st.subheader("Traffic Heatmap — Day × Hour")
df_heat = _load_heatmap()
if not df_heat.empty:
    import pandas as pd

    _day_map = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
    df_heat["day_name"] = df_heat["dow"].map(_day_map)
    pivot = df_heat.pivot_table(
        index="day_name",
        columns="hour_of_day",
        values="total_requests",
        fill_value=0,
    )
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])
    fig_heat = go.Figure(
        go.Heatmap(
            z=pivot.values.tolist(),
            x=[str(h) for h in pivot.columns.tolist()],
            y=pivot.index.tolist(),
            colorscale="Blues",
            hoverongaps=False,
            colorbar=dict(title="Requests"),
        )
    )
    fig_heat.update_layout(
        title="Request Volume by Day of Week and Hour",
        xaxis_title="Hour of Day (0–23)",
        yaxis_title="Day of Week",
        template="plotly_white",
    )
    st.plotly_chart(fig_heat, use_container_width=True)
else:
    st.info("No hourly traffic data available.")
