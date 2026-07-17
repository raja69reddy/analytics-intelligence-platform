"""Traffic & Sessions Overview — loads from vw_traffic and related views."""

import os
import sys
from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ai.anomaly_detection.detector import AnomalyDetector
from ai.anomaly_detection.train import load_model
from ai.anomaly_detection.utils import load_traffic_data
from dashboard.components.charts import bar_chart, line_chart, pie_chart
from dashboard.components.filters import (
    apply_filters,
    build_where_clause,
    get_channel_filter,
    get_date_filter,
    get_device_filter,
    get_page_filter,
    get_plotly_template,
    show_active_filters,
)
from dashboard.components.metrics import (
    calculate_period_change,
    display_4_kpi_row,
    format_duration,
    format_large_number,
    format_percentage,
)
from utils.db import query_df
from utils.query_runner import run_view

st.set_page_config(page_title="Traffic & Sessions", page_icon="📈", layout="wide")
st.title("📈 Traffic & Sessions Overview")
show_active_filters()

_plotly_tpl = get_plotly_template()


# ── Cached data loaders (TTL = 5 minutes) — date-filtered at DB level ─────────

@st.cache_data(ttl=300)
def _load_traffic(start_date=None, end_date=None, channels: tuple = ()):
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(f"SELECT * FROM vw_traffic {where}", params=params or None)


@st.cache_data(ttl=300)
def _load_daily(start_date=None, end_date=None):
    where, params = build_where_clause(start_date, end_date)
    return query_df(f"SELECT * FROM vw_daily_traffic {where}", params=params or None)


@st.cache_data(ttl=300)
def _load_channels(start_date=None, end_date=None, channels: tuple = ()):
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(f"""
WITH channel_totals AS (
    SELECT channel_grouping,
           SUM(sessions)                                                AS total_sessions,
           SUM(new_users)                                               AS total_new_users,
           SUM(pageviews)                                               AS total_pageviews,
           ROUND(AVG(session_duration_s)::numeric, 2)                   AS avg_session_duration,
           ROUND(100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)
               / NULLIF(SUM(sessions), 0), 2)                          AS bounce_rate_pct,
           COUNT(DISTINCT session_date)                                  AS active_days
    FROM raw_ga4_sessions {where}
    GROUP BY channel_grouping
),
grand_total AS (SELECT SUM(total_sessions) AS grand_sessions FROM channel_totals)
SELECT c.channel_grouping, c.total_sessions, c.total_new_users, c.total_pageviews,
       c.avg_session_duration, c.bounce_rate_pct, c.active_days,
       ROUND(100.0 * c.total_sessions / NULLIF(g.grand_sessions, 0), 2) AS channel_share_pct
FROM channel_totals c CROSS JOIN grand_total g
ORDER BY c.total_sessions DESC
""", params=params or None)


@st.cache_data(ttl=300)
def _load_devices(start_date=None, end_date=None):
    date_where, params = build_where_clause(start_date, end_date)
    where = (date_where + " AND device_category IS NOT NULL") if date_where else "WHERE device_category IS NOT NULL"
    return query_df(f"""
WITH device_totals AS (
    SELECT device_category,
           SUM(sessions)                                                AS total_sessions,
           SUM(new_users)                                               AS total_new_users,
           SUM(pageviews)                                               AS total_pageviews,
           ROUND(AVG(session_duration_s)::numeric, 2)                   AS avg_session_duration,
           ROUND(100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)
               / NULLIF(SUM(sessions), 0), 2)                          AS bounce_rate_pct
    FROM raw_ga4_sessions {where}
    GROUP BY device_category
),
grand_total AS (SELECT SUM(total_sessions) AS grand_sessions FROM device_totals)
SELECT d.device_category, d.total_sessions, d.total_new_users, d.total_pageviews,
       d.avg_session_duration, d.bounce_rate_pct,
       ROUND(100.0 * d.total_sessions / NULLIF(g.grand_sessions, 0), 2) AS device_share_pct
FROM device_totals d CROSS JOIN grand_total g
ORDER BY d.total_sessions DESC
""", params=params or None)


@st.cache_data(ttl=300)
def _load_newret(start_date=None, end_date=None):
    where, params = build_where_clause(start_date, end_date)
    return query_df(f"SELECT * FROM vw_new_vs_returning {where}", params=params or None)


@st.cache_data(ttl=300)
def _load_channel_daily(start_date=None, end_date=None, channels: tuple = ()):
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(
        f"""SELECT session_date, channel_grouping, SUM(sessions) AS sessions
            FROM raw_ga4_sessions {where}
            GROUP BY session_date, channel_grouping
            ORDER BY session_date, channel_grouping""",
        params=params or None,
    )


@st.cache_data(ttl=300)
def _load_pv_users(start_date=None, end_date=None):
    where, params = build_where_clause(start_date, end_date)
    return query_df(
        f"""SELECT session_date,
                   SUM(pageviews) AS total_pageviews,
                   SUM(new_users) AS total_users
            FROM raw_ga4_sessions {where}
            GROUP BY session_date ORDER BY session_date""",
        params=params or None,
    )


@st.cache_data(ttl=300)
def _load_geo(start_date=None, end_date=None):
    date_where, params = build_where_clause(start_date, end_date)
    where = (date_where + " AND country IS NOT NULL") if date_where else "WHERE country IS NOT NULL"
    return query_df(f"""
WITH country_totals AS (
    SELECT country,
           SUM(sessions)                                                AS total_sessions,
           SUM(new_users)                                               AS total_new_users,
           SUM(pageviews)                                               AS total_pageviews,
           ROUND(AVG(session_duration_s)::numeric, 2)                   AS avg_session_duration,
           ROUND(100.0 * SUM(CASE WHEN bounce THEN sessions ELSE 0 END)
               / NULLIF(SUM(sessions), 0), 2)                          AS bounce_rate_pct
    FROM raw_ga4_sessions {where}
    GROUP BY country
),
grand_total AS (SELECT SUM(total_sessions) AS grand_sessions FROM country_totals)
SELECT c.country, c.total_sessions, c.total_new_users, c.total_pageviews,
       c.avg_session_duration, c.bounce_rate_pct,
       ROUND(100.0 * c.total_sessions / NULLIF(g.grand_sessions, 0), 2) AS country_share_pct
FROM country_totals c CROSS JOIN grand_total g
ORDER BY c.total_sessions DESC
LIMIT 10
""", params=params or None)


# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    start_date, end_date = get_date_filter()
    channels = get_channel_filter()
    page_search = get_page_filter()
    devices = get_device_filter()
    st.divider()
    if st.button("Clear data cache"):
        st.cache_data.clear()
        st.success("Cache cleared — reloading…")
    st.caption("Cache TTL: 5 min")
    active = sum([bool(channels), bool(page_search), bool(devices)])
    if active:
        st.success(f"Filters applied: {active}")

# ── Load data — date range filtered at DB level ───────────────────────────────
try:
    with st.spinner("Loading traffic data from PostgreSQL…"):
        _ch = tuple(channels)
        df_traffic = _load_traffic(start_date, end_date, _ch)
        df_daily = _load_daily(start_date, end_date)
        df_channels = _load_channels(start_date, end_date, _ch)
        df_devices = _load_devices(start_date, end_date)
        df_newret = _load_newret(start_date, end_date)
        df_geo = _load_geo(start_date, end_date)
except Exception as exc:
    st.error(
        f"Could not load data from the database. "
        f"Check your PostgreSQL connection and try again.\n\n**Error:** {exc}"
    )
    st.stop()

with st.expander("Debug: data shapes", expanded=False):
    st.write(
        {
            "vw_traffic (filtered)": df_traffic.shape,
            "vw_daily_traffic (filtered)": df_daily.shape,
            "channel_performance (filtered)": df_channels.shape,
            "device_breakdown (filtered)": df_devices.shape,
            "vw_new_vs_returning (filtered)": df_newret.shape,
            "geo_performance (filtered)": df_geo.shape,
        }
    )

# Channel filter now applied at DB level via _load_traffic / _load_channels

# ── KPI cards — 4 core metrics with % change vs previous period ────────────────
period_days = (end_date - start_date).days + 1
prev_start = start_date - timedelta(days=period_days)
prev_end = start_date - timedelta(days=1)

df_prev = _load_traffic(prev_start, prev_end, tuple(channels))

curr_sessions = int(df_traffic["total_sessions"].sum())
curr_users = int(df_traffic["total_users"].sum())
curr_bounce = float(df_traffic["avg_bounce_rate"].mean()) if len(df_traffic) else 0.0
curr_duration = float(df_traffic["avg_session_duration"].mean()) if len(df_traffic) else 0.0

prev_sessions = int(df_prev["total_sessions"].sum())
prev_users = int(df_prev["total_users"].sum())
prev_bounce = float(df_prev["avg_bounce_rate"].mean()) if len(df_prev) else 0.0
prev_duration = float(df_prev["avg_session_duration"].mean()) if len(df_prev) else 0.0

display_4_kpi_row(
    {
        "title": "Total Sessions",
        "value": format_large_number(curr_sessions),
        "delta": calculate_period_change(curr_sessions, prev_sessions),
        "icon": "📈",
    },
    {
        "title": "Total Users",
        "value": format_large_number(curr_users),
        "delta": calculate_period_change(curr_users, prev_users),
        "icon": "👥",
    },
    {
        "title": "Avg Bounce Rate",
        "value": format_percentage(curr_bounce),
        "delta": calculate_period_change(curr_bounce, prev_bounce),
        "color": "inverse",
        "icon": "⬇️",
    },
    {
        "title": "Avg Session Duration",
        "value": format_duration(curr_duration),
        "delta": calculate_period_change(curr_duration, prev_duration),
        "icon": "⏱️",
    },
)
st.caption(
    f"Period: {start_date} to {end_date} vs {prev_start} to {prev_end}. "
    "Green = improved performance."
)

st.divider()

# ── Sessions over time with 7-day rolling average + range selectors ───────────
st.subheader("Sessions Over Time")
if not df_daily.empty:
    fig = line_chart(
        df_daily,
        x="session_date",
        y=["total_sessions", "sessions_7day_avg"],
        title="Daily Sessions with 7-Day Rolling Average",
        labels={"value": "Sessions", "session_date": "Date", "variable": "Metric"},
        template=_plotly_tpl,
    )
    fig.update_traces(
        selector={"name": "sessions_7day_avg"}, line={"dash": "dot", "width": 2}
    )
    fig.update_traces(
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Sessions: %{y:,}<extra></extra>",
        selector={"name": "total_sessions"},
    )
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=7, label="7D", step="day", stepmode="backward"),
                    dict(count=30, label="30D", step="day", stepmode="backward"),
                    dict(count=90, label="90D", step="day", stepmode="backward"),
                    dict(step="all", label="All"),
                ]
            ),
            rangeslider=dict(visible=False),
            type="date",
        ),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No daily traffic data available for the selected date range.")

st.divider()

# ── Pageviews and Users Over Time ─────────────────────────────────────────────
st.subheader("Pageviews & Users Over Time")
df_pv_users = _load_pv_users(start_date, end_date)
if not df_pv_users.empty:
    fig_pv = go.Figure()
    fig_pv.add_trace(
        go.Scatter(
            x=df_pv_users["session_date"],
            y=df_pv_users["total_pageviews"],
            name="Total Pageviews",
            mode="lines",
            line=dict(color="#636EFA", width=2),
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Pageviews: %{y:,}<extra></extra>",
        )
    )
    fig_pv.add_trace(
        go.Scatter(
            x=df_pv_users["session_date"],
            y=df_pv_users["total_users"],
            name="New Users",
            mode="lines",
            line=dict(color="#EF553B", width=2, dash="dot"),
            yaxis="y2",
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Users: %{y:,}<extra></extra>",
        )
    )
    fig_pv.update_layout(
        title="Daily Pageviews & New Users Over Time",
        xaxis=dict(
            title="Date",
            rangeselector=dict(
                buttons=[
                    dict(count=7, label="7D", step="day", stepmode="backward"),
                    dict(count=30, label="30D", step="day", stepmode="backward"),
                    dict(count=90, label="90D", step="day", stepmode="backward"),
                    dict(step="all", label="All"),
                ]
            ),
            type="date",
        ),
        yaxis=dict(title="Pageviews"),
        yaxis2=dict(title="New Users", overlaying="y", side="right"),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
        template=_plotly_tpl,
    )
    st.plotly_chart(fig_pv, use_container_width=True)
else:
    st.info("No pageviews data available for the selected date range.")

st.divider()

# ── AI Anomaly Detection ──────────────────────────────────────────────────────
st.subheader("🤖 AI Anomaly Detection")


@st.cache_data(ttl=300)
def _load_anomaly_results():
    try:
        model = load_model()
    except FileNotFoundError:
        return None, None
    df_full = load_traffic_data()
    if df_full.empty:
        return None, None
    detector = AnomalyDetector()
    detector._traffic_model = model
    annotated = detector.detect_traffic_anomalies(df_full)
    summary = detector.get_anomaly_summary(df_full)
    return annotated, summary


with st.spinner("Running AI anomaly detection…"):
    df_anomaly, anomaly_summary = _load_anomaly_results()

if df_anomaly is None:
    st.info(
        "Anomaly model not found. Run `python ai/anomaly_detection/train.py` to train it."
    )
else:
    anomaly_rows = df_anomaly[df_anomaly["is_anomaly"]]

    # Sessions chart with anomaly overlay
    if not df_daily.empty and not anomaly_rows.empty:
        fig_a = line_chart(
            df_daily,
            x="session_date",
            y=["total_sessions", "sessions_7day_avg"],
            title="Sessions Over Time with Anomaly Markers",
            labels={"value": "Sessions", "session_date": "Date", "variable": "Metric"},
            template=_plotly_tpl,
        )
        fig_a.update_traces(
            selector={"name": "sessions_7day_avg"}, line={"dash": "dot", "width": 2}
        )
        # Red dots on anomaly dates
        anomaly_dates_set = set(anomaly_rows["session_date"].astype(str))
        anom_daily = df_daily[
            df_daily["session_date"].astype(str).isin(anomaly_dates_set)
        ]
        if not anom_daily.empty:
            fig_a.add_scatter(
                x=anom_daily["session_date"],
                y=anom_daily["total_sessions"],
                mode="markers",
                marker={"color": "red", "size": 12, "symbol": "circle"},
                name="Anomaly",
            )
        st.plotly_chart(fig_a, use_container_width=True)
    elif not df_daily.empty:
        fig_a = line_chart(
            df_daily,
            x="session_date",
            y=["total_sessions", "sessions_7day_avg"],
            title="Sessions Over Time (no anomalies detected)",
            labels={"value": "Sessions", "session_date": "Date", "variable": "Metric"},
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_a, use_container_width=True)

    # Severity badges
    col_h, col_m, col_l = st.columns(3)
    col_h.metric("🔴 High Severity", anomaly_summary.severity_counts.get("high", 0))
    col_m.metric("🟡 Medium Severity", anomaly_summary.severity_counts.get("medium", 0))
    col_l.metric("🟢 Low Severity", anomaly_summary.severity_counts.get("low", 0))

    # Anomaly summary table
    if not anomaly_rows.empty:
        display_cols = [
            c
            for c in [
                "session_date",
                "total_sessions",
                "avg_bounce_rate",
                "anomaly_score",
                "severity",
            ]
            if c in anomaly_rows.columns
        ]
        st.dataframe(
            anomaly_rows[display_cols].sort_values("anomaly_score", ascending=False),
            use_container_width=True,
        )
    else:
        st.success("No anomalies detected in the current traffic data.")

st.divider()

st.subheader("Traffic by Channel")
col_left, col_right = st.columns(2)

with col_left:
    if not df_channels.empty:
        _bar_palette = [
            "#636EFA", "#EF553B", "#00CC96", "#AB63FA",
            "#FFA15A", "#19D3F3", "#FF6692", "#B6E880",
        ]
        df_ch_bar = df_channels.sort_values("total_sessions", ascending=True)
        _bar_colors = [
            _bar_palette[i % len(_bar_palette)] for i in range(len(df_ch_bar))
        ]
        fig_ch = go.Figure(
            go.Bar(
                x=df_ch_bar["total_sessions"],
                y=df_ch_bar["channel_grouping"],
                orientation="h",
                marker_color=_bar_colors,
                text=df_ch_bar["total_sessions"].apply(lambda v: f"{int(v):,}"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Sessions: %{x:,}<extra></extra>",
            )
        )
        fig_ch.update_layout(
            title="Sessions by Channel",
            xaxis_title="Sessions",
            yaxis_title="Channel",
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_ch, use_container_width=True)

with col_right:
    if not df_channels.empty:
        _donut_total = int(df_channels["total_sessions"].sum())
        fig_ch_donut = go.Figure(
            go.Pie(
                labels=df_channels["channel_grouping"],
                values=df_channels["total_sessions"],
                hole=0.4,
                textinfo="label+percent",
                hovertemplate=(
                    "<b>%{label}</b><br>Sessions: %{value:,}<br>Share: %{percent}<extra></extra>"
                ),
            )
        )
        fig_ch_donut.update_layout(
            title="Channel Distribution",
            annotations=[
                dict(
                    text=f"{_donut_total:,}<br>sessions",
                    x=0.5,
                    y=0.5,
                    font=dict(size=13),
                    showarrow=False,
                )
            ],
            legend=dict(orientation="v", x=1.0),
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_ch_donut, use_container_width=True)

st.divider()

# ── Sessions by Channel Over Time — Stacked Area ──────────────────────────────
st.subheader("Sessions by Channel Over Time")
df_ch_daily = _load_channel_daily(start_date, end_date, _ch)
if not df_ch_daily.empty:
    import pandas as _pd

    pivot_ch = df_ch_daily.pivot_table(
        index="session_date",
        columns="channel_grouping",
        values="sessions",
        fill_value=0,
    ).reset_index()

    _ch_colors = [
        "#636EFA", "#EF553B", "#00CC96", "#AB63FA",
        "#FFA15A", "#19D3F3", "#FF6692", "#B6E880",
    ]
    fig_area = go.Figure()
    _channel_cols = [c for c in pivot_ch.columns if c != "session_date"]
    for _i, _ch_name in enumerate(_channel_cols):
        _col = _ch_colors[_i % len(_ch_colors)]
        fig_area.add_trace(
            go.Scatter(
                x=pivot_ch["session_date"],
                y=pivot_ch[_ch_name],
                name=_ch_name,
                mode="lines",
                stackgroup="one",
                line=dict(color=_col, width=0.5),
                fillcolor=_col,
                hovertemplate=f"<b>%{{x|%Y-%m-%d}}</b><br>{_ch_name}: %{{y:,}}<extra></extra>",
            )
        )
    fig_area.update_layout(
        title="Sessions by Channel Over Time (Stacked Area)",
        xaxis_title="Date",
        yaxis_title="Sessions",
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.2),
        template=_plotly_tpl,
    )
    st.plotly_chart(fig_area, use_container_width=True)
else:
    st.info("No channel time-series data available for the selected period.")

st.divider()

# ── Traffic Period Comparison — Current vs Previous ───────────────────────────
st.subheader("Traffic Period Comparison")
_cmp_curr_pv = int(df_traffic["total_pageviews"].sum()) if not df_traffic.empty else 0
_cmp_prev_pv = int(df_prev["total_pageviews"].sum()) if not df_prev.empty else 0

_cmp_labels = ["Sessions", "Users", "Pageviews"]
_cmp_curr_vals = [curr_sessions, curr_users, _cmp_curr_pv]
_cmp_prev_vals = [prev_sessions, prev_users, _cmp_prev_pv]
_cmp_deltas = [
    calculate_period_change(c, p) for c, p in zip(_cmp_curr_vals, _cmp_prev_vals)
]

fig_cmp = go.Figure()
fig_cmp.add_trace(
    go.Bar(
        name=f"Current ({start_date} to {end_date})",
        x=_cmp_labels,
        y=_cmp_curr_vals,
        marker_color="#636EFA",
        text=_cmp_deltas,
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Current: %{y:,}<br>Change: %{text}<extra></extra>",
    )
)
fig_cmp.add_trace(
    go.Bar(
        name=f"Previous ({prev_start} to {prev_end})",
        x=_cmp_labels,
        y=_cmp_prev_vals,
        marker_color="#9EA6B5",
        hovertemplate="<b>%{x}</b><br>Previous: %{y:,}<extra></extra>",
    )
)
fig_cmp.update_layout(
    title=f"Period Comparison — Current vs Previous {period_days}-Day Window",
    xaxis_title="Metric",
    yaxis_title="Count",
    barmode="group",
    legend=dict(orientation="h", y=1.1),
    template=_plotly_tpl,
)
st.plotly_chart(fig_cmp, use_container_width=True)

st.divider()

st.subheader("New vs Returning Users")
if not df_newret.empty:
    _df_nr = df_newret.copy()
    _nr_total = _df_nr["new_user_sessions"] + _df_nr["returning_user_sessions"]
    _df_nr["new_pct"] = (
        _df_nr["new_user_sessions"] / _nr_total.replace(0, 1) * 100
    ).round(1)

    fig_nr = go.Figure()
    fig_nr.add_trace(
        go.Bar(
            name="New Users",
            x=_df_nr["session_date"],
            y=_df_nr["new_user_sessions"],
            marker_color="#636EFA",
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>New: %{y:,}<extra></extra>",
        )
    )
    fig_nr.add_trace(
        go.Bar(
            name="Returning Users",
            x=_df_nr["session_date"],
            y=_df_nr["returning_user_sessions"],
            marker_color="#FFA15A",
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Returning: %{y:,}<extra></extra>",
        )
    )
    fig_nr.add_trace(
        go.Scatter(
            name="New User %",
            x=_df_nr["session_date"],
            y=_df_nr["new_pct"],
            mode="lines",
            line=dict(color="#00CC96", width=2, dash="dot"),
            yaxis="y2",
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>New User %%: %{y:.1f}%%<extra></extra>",
        )
    )
    fig_nr.update_layout(
        barmode="stack",
        title="New vs Returning Users Over Time",
        xaxis_title="Date",
        yaxis=dict(title="Sessions"),
        yaxis2=dict(title="New User %", overlaying="y", side="right", range=[0, 100]),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
        template=_plotly_tpl,
    )
    st.plotly_chart(fig_nr, use_container_width=True)
else:
    st.info("No new vs returning data available.")

st.divider()

st.subheader("Device Breakdown")
if not df_devices.empty:
    col_dev1, col_dev2 = st.columns(2)
    _dev_colors = ["#636EFA", "#EF553B", "#00CC96"]
    with col_dev1:
        fig_dev_pie = go.Figure(
            go.Pie(
                labels=df_devices["device_category"],
                values=df_devices["total_sessions"],
                hole=0.35,
                textinfo="label+percent",
                marker=dict(colors=_dev_colors),
                hovertemplate=(
                    "<b>%{label}</b><br>Sessions: %{value:,}<br>Share: %{percent}<extra></extra>"
                ),
            )
        )
        fig_dev_pie.update_layout(
            title="Sessions by Device",
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_dev_pie, use_container_width=True)
    with col_dev2:
        fig_dev_bounce = go.Figure(
            go.Bar(
                x=df_devices["device_category"],
                y=df_devices["bounce_rate_pct"],
                marker_color=_dev_colors[: len(df_devices)],
                text=df_devices["bounce_rate_pct"].apply(lambda v: f"{v:.1f}%"),
                textposition="outside",
                hovertemplate=(
                    "<b>%{x}</b><br>Bounce Rate: %{y:.1f}%<extra></extra>"
                ),
            )
        )
        fig_dev_bounce.update_layout(
            title="Avg Bounce Rate by Device",
            xaxis_title="Device",
            yaxis_title="Bounce Rate (%)",
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_dev_bounce, use_container_width=True)
else:
    st.info("No device breakdown data available.")

st.divider()

# ── Geographic performance ────────────────────────────────────────────────────
st.subheader("Geographic Performance")
if not df_geo.empty:
    col_geo1, col_geo2 = st.columns(2)
    with col_geo1:
        st.dataframe(
            df_geo[
                ["country", "total_sessions", "country_share_pct", "bounce_rate_pct"]
            ],
            use_container_width=True,
        )
    with col_geo2:
        df_geo_sorted = df_geo.sort_values("total_sessions", ascending=True)
        fig_geo = bar_chart(
            df_geo_sorted,
            x="total_sessions",
            y="country",
            title="Top Countries by Sessions",
            orientation="h",
            labels={"country": "Country", "total_sessions": "Sessions"},
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_geo, use_container_width=True)
else:
    st.info("No geographic data available.")

st.divider()

# ── Raw data table + CSV download ─────────────────────────────────────────────
st.subheader("Raw Traffic Data")
st.caption(
    f"Last updated: {date.today().strftime('%Y-%m-%d')} · {len(df_traffic):,} rows after filters"
)

if not df_traffic.empty:
    st.dataframe(
        df_traffic.sort_values("session_date", ascending=False),
        use_container_width=True,
        height=400,
    )
    csv_bytes = df_traffic.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered data as CSV",
        data=csv_bytes,
        file_name="traffic_data.csv",
        mime="text/csv",
    )
else:
    st.info("No traffic data available for the selected filters.")
