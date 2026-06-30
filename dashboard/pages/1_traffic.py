"""Traffic & Sessions Overview — loads from vw_traffic and related views."""
import os
import sys
from datetime import timedelta

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.charts import bar_chart, line_chart, pie_chart
from dashboard.components.filters import (
    apply_filters,
    get_channel_filter,
    get_date_filter,
    get_device_filter,
    get_page_filter,
)
from dashboard.components.metrics import (
    display_kpi_row,
    format_duration,
    format_number,
    format_percentage,
)
from utils.query_runner import run_view

st.set_page_config(page_title="Traffic & Sessions", page_icon="📈", layout="wide")
st.title("📈 Traffic & Sessions Overview")

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    start_date, end_date = get_date_filter()
    channels    = get_channel_filter()
    page_search = get_page_filter()
    devices     = get_device_filter()
    active = sum([bool(channels), bool(page_search), bool(devices)])
    if active:
        st.success(f"Filters applied: {active}")

# ── Load data ─────────────────────────────────────────────────────────────────
df_traffic  = run_view("vw_traffic")
df_daily    = run_view("vw_daily_traffic")
df_channels = run_view("vw_channel_performance")
df_devices  = run_view("vw_device_breakdown")
df_newret   = run_view("vw_new_vs_returning")

# Debug: verify each view returned rows
with st.expander("Debug: data shapes", expanded=False):
    st.write({
        "vw_traffic":             df_traffic.shape,
        "vw_daily_traffic":       df_daily.shape,
        "vw_channel_performance": df_channels.shape,
        "vw_device_breakdown":    df_devices.shape,
        "vw_new_vs_returning":    df_newret.shape,
    })

# Apply date / channel filters
df_traffic = apply_filters(df_traffic, start_date, end_date, channels)
df_daily   = apply_filters(df_daily,   start_date, end_date)

# ── KPI cards with % change vs previous period ────────────────────────────────
period_days = (end_date - start_date).days + 1
prev_start  = start_date - timedelta(days=period_days)
prev_end    = start_date - timedelta(days=1)

df_all  = run_view("vw_traffic")
df_prev = apply_filters(df_all, prev_start, prev_end, channels)

def _delta(curr: float, prev: float) -> str | None:
    if prev == 0:
        return None
    return f"{((curr - prev) / prev * 100):+.1f}%"

curr_sessions  = int(df_traffic["total_sessions"].sum())
curr_users     = int(df_traffic["total_users"].sum())
curr_pageviews = int(df_traffic["total_pageviews"].sum())
curr_bounce    = float(df_traffic["avg_bounce_rate"].mean()) if len(df_traffic) else 0.0
curr_duration  = float(df_traffic["avg_session_duration"].mean()) if len(df_traffic) else 0.0

prev_sessions  = int(df_prev["total_sessions"].sum())
prev_users     = int(df_prev["total_users"].sum())
prev_pageviews = int(df_prev["total_pageviews"].sum())
prev_bounce    = float(df_prev["avg_bounce_rate"].mean()) if len(df_prev) else 0.0
prev_duration  = float(df_prev["avg_session_duration"].mean()) if len(df_prev) else 0.0

display_kpi_row([
    {"title": "Total Sessions",       "value": format_number(curr_sessions),
     "delta": _delta(curr_sessions, prev_sessions)},
    {"title": "Total Users",          "value": format_number(curr_users),
     "delta": _delta(curr_users, prev_users)},
    {"title": "Total Pageviews",      "value": format_number(curr_pageviews),
     "delta": _delta(curr_pageviews, prev_pageviews)},
    {"title": "Avg Bounce Rate",      "value": format_percentage(curr_bounce),
     "delta": _delta(curr_bounce, prev_bounce), "delta_color": "inverse"},
    {"title": "Avg Session Duration", "value": format_duration(curr_duration),
     "delta": _delta(curr_duration, prev_duration)},
])

st.divider()

# ── Sessions over time with 7-day rolling average ─────────────────────────────
st.subheader("Sessions Over Time")
if not df_daily.empty:
    fig = line_chart(
        df_daily, x="session_date",
        y=["total_sessions", "sessions_7day_avg"],
        title="Daily Sessions with 7-Day Rolling Average",
        labels={"value": "Sessions", "session_date": "Date", "variable": "Metric"},
    )
    fig.update_traces(selector={"name": "sessions_7day_avg"}, line={"dash": "dot", "width": 2})
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No daily traffic data available for the selected date range.")

st.subheader("Traffic by Channel")
col_left, col_right = st.columns(2)

with col_left:
    if not df_channels.empty:
        # Sort ascending so that the longest bar appears at the top in a horizontal chart
        df_ch_sorted = df_channels.sort_values("total_sessions", ascending=True)
        fig_ch = bar_chart(
            df_ch_sorted, x="total_sessions", y="channel_grouping",
            title="Sessions by Channel (Descending)",
            orientation="h",
            labels={"channel_grouping": "Channel", "total_sessions": "Sessions"},
        )
        st.plotly_chart(fig_ch, use_container_width=True)

with col_right:
    if not df_channels.empty:
        fig_ch_pie = pie_chart(
            df_channels, names="channel_grouping", values="total_sessions",
            title="Channel Distribution",
        )
        st.plotly_chart(fig_ch_pie, use_container_width=True)

st.divider()

st.subheader("New vs Returning Users")
if not df_newret.empty:
    import plotly.graph_objects as go
    fig_nr = go.Figure()
    fig_nr.add_trace(go.Bar(
        name="New Users",
        x=df_newret["session_date"],
        y=df_newret["new_user_sessions"],
    ))
    fig_nr.add_trace(go.Bar(
        name="Returning Users",
        x=df_newret["session_date"],
        y=df_newret["returning_user_sessions"],
    ))
    fig_nr.update_layout(
        barmode="stack",
        title="New vs Returning Users Over Time",
        xaxis_title="Date",
        yaxis_title="Sessions",
        template="plotly_white",
    )
    st.plotly_chart(fig_nr, use_container_width=True)
else:
    st.info("No new vs returning data available.")

st.divider()

st.subheader("Sessions by Device")
if not df_devices.empty:
    fig_dev = bar_chart(
        df_devices, x="device_category", y="total_sessions",
        title="Device Category Breakdown",
        labels={"device_category": "Device", "total_sessions": "Sessions"},
    )
    st.plotly_chart(fig_dev, use_container_width=True)
