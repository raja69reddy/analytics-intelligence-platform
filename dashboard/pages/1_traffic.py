"""Traffic & Sessions Overview — loads from vw_traffic and related views."""

import os
import sys
from datetime import date, timedelta

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
    display_kpi_row,
    format_duration,
    format_number,
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

# ── KPI cards with % change vs previous period ────────────────────────────────
period_days = (end_date - start_date).days + 1
prev_start = start_date - timedelta(days=period_days)
prev_end = start_date - timedelta(days=1)

df_prev = _load_traffic(prev_start, prev_end, tuple(channels))


def _delta(curr: float, prev: float) -> str | None:
    if prev == 0:
        return None
    return f"{((curr - prev) / prev * 100):+.1f}%"


curr_sessions = int(df_traffic["total_sessions"].sum())
curr_users = int(df_traffic["total_users"].sum())
curr_pageviews = int(df_traffic["total_pageviews"].sum())
curr_bounce = float(df_traffic["avg_bounce_rate"].mean()) if len(df_traffic) else 0.0
curr_duration = (
    float(df_traffic["avg_session_duration"].mean()) if len(df_traffic) else 0.0
)

prev_sessions = int(df_prev["total_sessions"].sum())
prev_users = int(df_prev["total_users"].sum())
prev_pageviews = int(df_prev["total_pageviews"].sum())
prev_bounce = float(df_prev["avg_bounce_rate"].mean()) if len(df_prev) else 0.0
prev_duration = float(df_prev["avg_session_duration"].mean()) if len(df_prev) else 0.0

display_kpi_row(
    [
        {
            "title": "Total Sessions",
            "value": format_number(curr_sessions),
            "delta": _delta(curr_sessions, prev_sessions),
        },
        {
            "title": "Total Users",
            "value": format_number(curr_users),
            "delta": _delta(curr_users, prev_users),
        },
        {
            "title": "Total Pageviews",
            "value": format_number(curr_pageviews),
            "delta": _delta(curr_pageviews, prev_pageviews),
        },
        {
            "title": "Avg Bounce Rate",
            "value": format_percentage(curr_bounce),
            "delta": _delta(curr_bounce, prev_bounce),
            "delta_color": "inverse",
        },
        {
            "title": "Avg Session Duration",
            "value": format_duration(curr_duration),
            "delta": _delta(curr_duration, prev_duration),
        },
    ]
)

st.divider()

# ── Sessions over time with 7-day rolling average ─────────────────────────────
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
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No daily traffic data available for the selected date range.")

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
        # Sort ascending so that the longest bar appears at the top in a horizontal chart
        df_ch_sorted = df_channels.sort_values("total_sessions", ascending=True)
        fig_ch = bar_chart(
            df_ch_sorted,
            x="total_sessions",
            y="channel_grouping",
            title="Sessions by Channel (Descending)",
            orientation="h",
            labels={"channel_grouping": "Channel", "total_sessions": "Sessions"},
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_ch, use_container_width=True)

with col_right:
    if not df_channels.empty:
        fig_ch_pie = pie_chart(
            df_channels,
            names="channel_grouping",
            values="total_sessions",
            title="Channel Distribution",
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_ch_pie, use_container_width=True)

st.divider()

st.subheader("New vs Returning Users")
if not df_newret.empty:
    import plotly.graph_objects as go

    fig_nr = go.Figure()
    fig_nr.add_trace(
        go.Bar(
            name="New Users",
            x=df_newret["session_date"],
            y=df_newret["new_user_sessions"],
        )
    )
    fig_nr.add_trace(
        go.Bar(
            name="Returning Users",
            x=df_newret["session_date"],
            y=df_newret["returning_user_sessions"],
        )
    )
    fig_nr.update_layout(
        barmode="stack",
        title="New vs Returning Users Over Time",
        xaxis_title="Date",
        yaxis_title="Sessions",
        template=_plotly_tpl,
    )
    st.plotly_chart(fig_nr, use_container_width=True)
else:
    st.info("No new vs returning data available.")

st.divider()

st.subheader("Device Breakdown")
if not df_devices.empty:
    col_dev1, col_dev2 = st.columns(2)
    with col_dev1:
        fig_dev_pie = pie_chart(
            df_devices,
            names="device_category",
            values="total_sessions",
            title="Sessions by Device",
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_dev_pie, use_container_width=True)
    with col_dev2:
        fig_dev_bounce = bar_chart(
            df_devices,
            x="device_category",
            y="avg_bounce_rate",
            title="Avg Bounce Rate by Device",
            labels={"device_category": "Device", "avg_bounce_rate": "Bounce Rate (%)"},
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
